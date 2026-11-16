from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.incidents import find, authenticate, stamp
from app.models import now
from app.execution_backends import backend_name
from app.investigation_models import Investigation, InvestigationEvent, ACTIVE, TERMINAL

router=APIRouter(prefix='/api',tags=['Investigations'])


def manager(request:Request):
    value=getattr(request.app.state,'investigations',None)
    if value is None: raise HTTPException(503,'Investigation worker unavailable')
    return value


def authorize(request:Request, authorization:Annotated[str|None,Header()]=None):
    settings=manager(request).settings
    if settings.environment!='development' or request.client.host not in ('127.0.0.1','::1'):
        raise HTTPException(403,'Agent actions require a local development client')
    authenticate(authorization,settings.agent_auth_token)


def serialize(row,detail=False):
    result={key:getattr(row,key) for key in ('id','incident_id','service_name','status','duration_ms','error_code','error_message','execution_metadata')}
    result.update({key:stamp(getattr(row,key)) for key in ('created_at','started_at','completed_at')})
    result['root_cause_summary']=row.report.get('suspected_root_cause',{}).get('statement') if row.report else None
    if detail: result.update(evidence=row.evidence,report=row.report)
    return result


def job(db,id):
    row=db.get(Investigation,str(id))
    if row is None: raise HTTPException(404,'Investigation not found')
    return row


class StartInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    authorize_paid_execution: Literal[True] | None = None
    authorize_local_execution: Literal[True] | None = None
    @field_validator('authorize_paid_execution','authorize_local_execution',mode='before')
    @classmethod
    def explicit_true(cls,value):
        if value is not True: raise ValueError('Explicit boolean true is required')
        return value


@router.get('/investigations/configuration')
async def configuration(worker=Depends(manager)):
    if backend_name(worker.adapter) == 'local-ollama':
        await worker.adapter.probe()
    return {**worker.adapter.status(),'backend':backend_name(worker.adapter),'authentication_required':True,'read_only':worker.adapter.mode!='live-managed-codex',
        'paid_authorization_required':backend_name(worker.adapter) != 'local-ollama','project_source_scope':'services/shared, services/fixtures and the affected service directory'}


@router.get('/investigations/readiness')
async def readiness(worker=Depends(manager)):
    if backend_name(worker.adapter) != 'local-ollama':
        return {'backend':backend_name(worker.adapter),'model_configured':False,
                'memory_guard':'not_applicable','live_inference_verified':False,
                'verification_status':'pending','can_start':False,'read_only':True,
                'error_code':'LOCAL_BACKEND_NOT_SELECTED'}
    return await worker.adapter.readiness()


class StopAcknowledgment(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    confirm_runtime_stopped: bool


@router.post('/investigations/runtime/acknowledge-stop',dependencies=[Depends(authorize)])
async def acknowledge_stop(body:StopAcknowledgment,worker=Depends(manager),db:Session=Depends(get_db)):
    if body.confirm_runtime_stopped is not True or backend_name(worker.adapter) != 'local-ollama':
        raise HTTPException(422,'Explicit local runtime stop acknowledgment required')
    if worker.current is not None or db.scalar(select(func.count()).select_from(Investigation).where(Investigation.status.in_(ACTIVE))):
        raise HTTPException(409,'Cancel or finish outstanding investigations first')
    try:
        await worker.adapter.acknowledge_stop()
    except Exception:
        raise HTTPException(503,'Ollama must be reachable with no loaded models before reconciliation') from None
    for row in db.scalars(select(Investigation)):
        if (row.execution_metadata or {}).get('backend') == 'local-ollama' and (row.execution_metadata or {}).get('local_stop_state') in ('possibly_running','unconfirmed'):
            row.execution_metadata={**row.execution_metadata,'local_stop_state':'operator_reconciled'}
            db.add(InvestigationEvent(investigation_id=row.id,status=row.status,message='Authorized operator acknowledged runtime stop; Ollama reported no loaded models. No inference resumed.'))
    db.commit()
    return {'acknowledged':True,'generation_resumed':False}


@router.post('/incidents/{incident_id}/investigate',status_code=202,dependencies=[Depends(authorize)])
async def create(incident_id:UUID,body:StartInput,worker=Depends(manager),db:Session=Depends(get_db)):
    incident=find(db,incident_id)
    local = backend_name(worker.adapter) == 'local-ollama'
    if (body.authorize_local_execution if local else body.authorize_paid_execution) is not True:
        raise HTTPException(422,'Explicit authorization for the selected execution backend is required')
    if local:
        await worker.adapter.probe()
    if not worker.adapter.status().get('available'): raise HTTPException(503,'Selected execution backend unavailable. No fallback or simulated analysis is substituted.')
    if db.bind.dialect.name=='sqlite':
        # End the lookup's read transaction before taking a reserved write lock.
        db.rollback();db.connection().exec_driver_sql('BEGIN IMMEDIATE')
    existing=db.scalar(select(Investigation).where(Investigation.incident_id==str(incident_id),Investigation.status.in_(ACTIVE)))
    if existing: raise HTTPException(409,detail={'message':'An investigation is already active','investigation_id':existing.id})
    count=db.scalar(select(func.count()).select_from(Investigation).where(Investigation.status.in_(ACTIVE)))
    if count>=worker.settings.agent_queue_limit: raise HTTPException(429,'Investigation queue capacity reached')
    row=Investigation(incident_id=str(incident_id),service_name=incident.service_name,status='QUEUED',execution_metadata={'mode':worker.adapter.mode,'backend':backend_name(worker.adapter),'execution_authorized':True})
    db.add(row)
    try:
        db.flush();db.add(InvestigationEvent(investigation_id=row.id,status='QUEUED',message='Explicitly authorized investigation queued.'))
        db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'An investigation is already active') from None
    worker.notify()
    return {'investigation':serialize(row)}


@router.get('/investigations/summary')
def summary(db:Session=Depends(get_db)):
    count=lambda statuses:db.scalar(select(func.count()).select_from(Investigation).where(Investigation.status.in_(statuses)))
    return {'total':count(ACTIVE+TERMINAL),'running':count(ACTIVE),'completed':count(('COMPLETED',)),
        'failed':count(('FAILED',)),'cancelled':count(('CANCELLED',)),
        'average_duration_ms':db.scalar(select(func.avg(Investigation.duration_ms)).where(Investigation.status=='COMPLETED'))}


@router.get('/investigations')
def listing(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),incident_id:UUID|None=None,db:Session=Depends(get_db)):
    filters=[Investigation.incident_id==str(incident_id)] if incident_id else []
    total=db.scalar(select(func.count()).select_from(Investigation).where(*filters))
    rows=db.scalars(select(Investigation).where(*filters).order_by(Investigation.created_at.desc(),Investigation.id).offset((page-1)*page_size).limit(page_size))
    return {'items':[serialize(row) for row in rows],'total':total,'page':page,'page_size':page_size}


@router.get('/investigations/{id}')
def detail(id:UUID,db:Session=Depends(get_db)):
    return {'investigation':serialize(job(db,id),True)}


@router.get('/investigations/{id}/events')
def events(id:UUID,page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=100),db:Session=Depends(get_db)):
    job(db,id)
    total=db.scalar(select(func.count()).select_from(InvestigationEvent).where(InvestigationEvent.investigation_id==str(id)))
    rows=db.scalars(select(InvestigationEvent).where(InvestigationEvent.investigation_id==str(id)).order_by(InvestigationEvent.id).offset((page-1)*page_size).limit(page_size))
    return {'items':[{'id':row.id,'timestamp':stamp(row.timestamp),'status':row.status,'message':row.message} for row in rows], 'total':total,'page':page,'page_size':page_size}


@router.get('/investigations/{id}/report')
def report(id:UUID,db:Session=Depends(get_db)):
    row=job(db,id)
    if row.status!='COMPLETED' or row.report is None: raise HTTPException(409,'No completed report is available')
    return {'report':row.report}


@router.post('/investigations/{id}/cancel',dependencies=[Depends(authorize)])
def cancel(id:UUID,worker=Depends(manager),db:Session=Depends(get_db)):
    if db.bind.dialect.name == 'sqlite': db.connection().exec_driver_sql('BEGIN IMMEDIATE')
    row=job(db,id)
    if row.status in TERMINAL: raise HTTPException(409,'Investigation is already terminal')
    row.status='CANCELLED';row.completed_at=now();row.error_code='CANCELLED';row.error_message='Cancelled by an authorized local operator.'
    if row.started_at: row.duration_ms=round((row.completed_at-row.started_at).total_seconds()*1000,2)
    db.add(InvestigationEvent(investigation_id=row.id,status='CANCELLED',message=row.error_message));db.commit()
    worker.cancel(str(id))
    return {'investigation':serialize(row)}
