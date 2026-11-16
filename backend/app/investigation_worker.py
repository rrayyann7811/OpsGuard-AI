import asyncio
import json
from pathlib import Path
from sqlalchemy import select
from app.models import Incident, IncidentEvent, now
from app.investigation_models import Investigation, InvestigationEvent, ACTIVE, TERMINAL
from app.agent_evidence import RepositoryReader, sanitize
from app.agent_reports import validate_analysis
from app.execution_backends import create_adapter, backend_name
from app.managed_codex_adapter import ManagedCodexAdapter


def lock_write(db):
    if db.bind.dialect.name == 'sqlite':
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')


class InvestigationManager:
    def __init__(self,settings,factory,knowledge,adapter=None):
        self.settings,self.factory,self.knowledge=settings,factory,knowledge
        self.adapter=adapter if adapter is not None else create_adapter(settings)
        self.recovery=[]
        self.wakeup=asyncio.Event()
        self.stopping=False
        self.task=None
        self.current=None
        self.current_id=None
        self.loop=None

    def recover(self):
        with self.factory() as db:
            for row in db.scalars(select(Investigation).where(Investigation.status.in_(ACTIVE))):
                if (row.execution_metadata or {}).get('backend') == 'local-ollama':
                    row.execution_metadata={**(row.execution_metadata or {}),'local_stop_state':'unconfirmed'}
                row.status='FAILED';row.completed_at=now();row.error_code='BACKEND_RESTART'
                row.error_message='Backend stopped before investigation completion. No paid run was resumed automatically.'
                db.add(InvestigationEvent(investigation_id=row.id,status='FAILED',message=row.error_message))
            db.commit()
            if backend_name(self.adapter) == 'local-ollama':
                self.adapter._unresolved=any((row.execution_metadata or {}).get('backend') == 'local-ollama'
                    and (row.execution_metadata or {}).get('local_stop_state') in ('possibly_running','unconfirmed')
                    for row in db.scalars(select(Investigation)))
            self.recovery=[(row.id,dict(row.execution_metadata or {})) for row in db.scalars(select(Investigation))
                           if (row.execution_metadata or {}).get('backend')=='managed-codex'
                           and (row.execution_metadata or {}).get('cleanup_state') in ('creating','active','unknown','pending')]

    def journal(self, id, changes):
        # Lifecycle metadata must survive cancellation/failure and subsequent stage updates.
        with self.factory() as db:
            lock_write(db)
            row=db.get(Investigation,id)
            if row is None: raise ValueError('Investigation journal missing')
            row.execution_metadata={**(row.execution_metadata or {}),**changes}
            db.commit()

    def start(self):
        self.recover()
        self.loop=asyncio.get_running_loop()
        self.task=asyncio.create_task(self.work())

    def notify(self):
        if self.loop: self.loop.call_soon_threadsafe(self.wakeup.set)

    async def stop(self):
        self.stopping=True;self.wakeup.set()
        if self.current: self.current.cancel()
        if self.task: await self.task
        if isinstance(self.adapter, ManagedCodexAdapter): await self.adapter.aclose()
        # Queued/unfinished rows are marked FAILED on the next startup, never COMPLETED.

    def cancel(self,id):
        if self.loop and self.current_id==id and self.current:
            self.loop.call_soon_threadsafe(self.current.cancel)
        self.notify()

    def update(self,id,status,message,evidence=None,metadata=None):
        with self.factory() as db:
            lock_write(db)
            row=db.get(Investigation,id)
            if row is None or row.status in TERMINAL: raise asyncio.CancelledError()
            transitions=dict(zip(ACTIVE[:-1],ACTIVE[1:]))
            if status != row.status and transitions.get(row.status) != status:
                raise ValueError('Invalid investigation state transition')
            row.status=status
            if row.started_at is None: row.started_at=now()
            if evidence is not None: row.evidence=evidence
            if metadata is not None: row.execution_metadata={**(row.execution_metadata or {}),**metadata}
            db.add(InvestigationEvent(investigation_id=id,status=status,message=message))
            db.commit()

    async def work(self):
        for id,metadata in self.recovery:
            if isinstance(self.adapter,ManagedCodexAdapter):
                try:
                    await self.adapter.reconcile(metadata,lambda changes,id=id:self.journal(id,changes))
                except Exception:
                    self.adapter._unresolved=True
                    self.journal(id,{'cleanup_state':'pending','remote_error_code':'RECOVERY_FAILED'})
            else:
                self.journal(id,{'cleanup_state':'pending','remote_error_code':'RECOVERY_CLIENT_UNAVAILABLE'})
        self.recovery=[]
        while not self.stopping:
            with self.factory() as db:
                queued=db.scalar(select(Investigation).where(Investigation.status=='QUEUED').order_by(Investigation.created_at).limit(1))
                id=queued.id if queued else None
            if not id:
                self.wakeup.clear()
                try: await asyncio.wait_for(self.wakeup.wait(),1)
                except asyncio.TimeoutError: pass
                continue
            self.current_id=id
            self.current=asyncio.create_task(self.run_one(id))
            try: await self.current
            except asyncio.CancelledError: pass
            finally: self.current=None;self.current_id=None

    async def run_one(self,id):
        evidence=[];limitations=[]
        def add(item):
            if len(evidence)>=70: return
            item={**item,'id':f'E{len(evidence)+1:03}'}
            # Sanitize all textual payloads, including historical snippets and source code.
            def clean(value):
                if isinstance(value,str):
                    text=sanitize(value)
                    for root in {self.settings.agent_project_root,str(Path(__file__).resolve().parents[2])}:
                        text=text.replace(root,'<approved-repo>')
                    return text
                if isinstance(value,list): return [clean(item) for item in value]
                if isinstance(value,dict): return {key:clean(item) for key,item in value.items()}
                return value
            cleaned=clean(item)
            if len(json.dumps(evidence+[cleaned]))>110000:
                limitations.append('Evidence bundle reached its size bound; some context was omitted.')
                return
            evidence.append(cleaned)
        try:
            async with asyncio.timeout(self.settings.agent_timeout_seconds):
                with self.factory() as db:
                    queued=db.get(Investigation,id)
                    selected=(queued.execution_metadata or {}).get('backend')
                    if selected and selected != backend_name(self.adapter):
                        raise ValueError('Queued backend changed; no fallback permitted')
                self.update(id,'COLLECTING_EVIDENCE','Reading persisted incident and recent request evidence.')
                with self.factory() as db:
                    job=db.get(Investigation,id);row=db.get(Incident,job.incident_id)
                    incident={key:getattr(row,key) for key in ('id','service_name','title','error_type','error_message','stack_trace','endpoint','http_status','occurrence_count')}
                    add({'kind':'log','content':json.dumps(incident)})
                    events=db.scalars(select(IncidentEvent).where(IncidentEvent.incident_id==row.id).order_by(IncidentEvent.id.desc()).limit(4))
                    for event in events: add({'kind':'log','request_id':event.request_id,'event_id':event.event_id,'content':json.dumps(event.evidence)})
                self.update(id,'RETRIEVING_CONTEXT','Searching existing historical index (supporting context, not causal proof).',evidence)
                query='\n'.join(str(incident.get(key) or '') for key in ('service_name','title','error_type','error_message','stack_trace'))[:6000]
                matches=[]
                for attempt in range(2):
                    try:
                        matches=await asyncio.to_thread(self.knowledge.search,query,top_k=3,service=incident['service_name'])
                        break
                    except Exception:
                        if attempt==0: await asyncio.sleep(.05)
                        else: limitations.append('Historical retrieval unavailable after two bounded read-only attempts.')
                if not matches: limitations.append('No historical matches were supplied; retrieved context is not proof.')
                for match in matches:
                    add({'kind':'historical','historical_id':match['incident']['id'], 'similarity_score':match['similarity_score'],
                        'source_ref':match['source_ref'],'content':json.dumps(match['incident'])})
                self.update(id,'INSPECTING_CODE','Reading approved source excerpts and correlating error/stack locations.',evidence)
                reader=RepositoryReader(self.settings.agent_project_root)
                sources=await asyncio.to_thread(reader.collect,incident['service_name'],incident)
                if not sources: limitations.append('No relevant source files were available in approved directories.')
                for source in sources:
                    add(source)
                    self.update(id,'INSPECTING_CODE',f"source.read {source['path']} (collected range {source['start_line']}-{source['end_line']})",evidence)
                self.update(id,'ANALYZING_GIT','Inspecting scoped Git log/show/diff/blame/status with fixed command arguments.',evidence)
                git,missing=await asyncio.to_thread(reader.collect_git,sources)
                limitations.extend(missing)
                for item in git:
                    add(item)
                    self.update(id,'ANALYZING_GIT',f"git.{item['operation']} collected within approved source paths.",evidence)
                self.update(id,'GENERATING_REPORT',('Running explicit TEST DOUBLE (not genuine AI); validating schema and evidence references.' if self.adapter.mode == 'test-double' else 'Local AI Investigation: analyzing collected evidence without tools.' if backend_name(self.adapter) == 'local-ollama' else 'Running authorized agent analysis; validating schema and evidence references.'),evidence,{'mode':self.adapter.mode})
                bundle={'investigation_id':id,'incident_id':incident['id'],'service_name':incident['service_name'],
                    'evidence':evidence,'limitations':limitations,'read_only':True}
                if isinstance(self.adapter,ManagedCodexAdapter):
                    with self.factory() as db:
                        authorized=(db.get(Investigation,id).execution_metadata or {}).get('execution_authorized') is True
                    result=await self.adapter.run(bundle,authorized=authorized,journal=lambda changes:self.journal(id,changes))
                else:
                    if backend_name(self.adapter) == 'local-ollama':
                        self.journal(id,{'local_stop_state':'possibly_running'})
                    result=await self.adapter.run(bundle)
                analysis=validate_analysis(result['analysis'],evidence,limitations)
                if backend_name(self.adapter) == 'local-ollama' and analysis['suspected_root_cause']['classification'] == 'uncertain':
                    analysis['confidence']={'category':'INSUFFICIENT_EVIDENCE','reason':'The local model could not establish a supported root-cause hypothesis.'}
                # Store only safe execution metadata, never prompts/credentials or private reasoning.
                metadata={key:result.get('metadata',{}).get(key) for key in ('mode','provider','sdk','model','thread_id','usage','sandbox','session_id','model_digest','metrics','submitted_evidence_ids')}
                metadata['mode']=self.adapter.mode
                metadata['backend']=backend_name(self.adapter)
                if metadata['backend'] == 'local-ollama': metadata['local_stop_state']='generation_completed'
                with self.factory() as db:
                    lock_write(db)
                    job=db.get(Investigation,id)
                    if job.status in TERMINAL: return
                    job.status='COMPLETED';job.completed_at=now()
                    job.duration_ms=round((job.completed_at-job.started_at).total_seconds()*1000,2)
                    job.execution_metadata={**(job.execution_metadata or {}),**metadata};job.evidence=evidence
                    job.report={**analysis,'error_summary':sanitize(incident['error_type']+': '+incident['error_message']),'investigation_id':id,'incident_id':job.incident_id,'affected_service':job.service_name,
                        'duration_ms':job.duration_ms,'execution_mode':self.adapter.mode,
                        'supporting_log_evidence':[item['id'] for item in evidence if item['kind']=='log']}
                    db.add(InvestigationEvent(investigation_id=id,status='COMPLETED',message='Structured report passed provenance validation. No source changes were made.'))
                    db.commit()
        except asyncio.CancelledError:
            if backend_name(self.adapter) == 'local-ollama':
                self.journal(id,{'local_stop_state':'unconfirmed' if self.adapter._unresolved else 'not_submitted'})
            self.finish_failure(id,'CANCELLED','CANCELLED','Investigation cancelled; no report accepted.',evidence)
        except TimeoutError:
            if backend_name(self.adapter) == 'local-ollama':
                self.journal(id,{'local_stop_state':'unconfirmed' if self.adapter._unresolved else 'not_submitted'})
            self.finish_failure(id,'FAILED','TIMEOUT','Investigation exceeded its bounded execution deadline.',evidence)
        except Exception as error:
            from app.ollama_adapter import OllamaError
            code=error.code if isinstance(error,OllamaError) else 'INVESTIGATION_FAILED'
            if backend_name(self.adapter) == 'local-ollama':
                self.journal(id,{'local_stop_state':'unconfirmed' if self.adapter._unresolved else 'not_running'})
            self.finish_failure(id,'FAILED',code,'Evidence collection, agent execution or report validation failed. No report was accepted.',evidence)

    def finish_failure(self,id,status,code,message,evidence):
        with self.factory() as db:
            lock_write(db)
            row=db.get(Investigation,id)
            if row is None or row.status in TERMINAL: return
            row.status=status;row.error_code=code;row.error_message=message;row.completed_at=now();row.evidence=evidence
            if row.started_at: row.duration_ms=round((row.completed_at-row.started_at).total_seconds()*1000,2)
            db.add(InvestigationEvent(investigation_id=id,status=status,message=message));db.commit()
