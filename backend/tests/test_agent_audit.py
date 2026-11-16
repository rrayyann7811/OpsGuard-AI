"""Final Phase 5 security audit. No paid SDK calls."""
import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch
import pytest
from pydantic import SecretStr
from sqlalchemy import event
from app.agent_evidence import RepositoryReader
from app.agent_reports import AgentAnalysis,validate_analysis
from app.codex_adapter import CodexAdapter
from app.config import Settings
from app.investigation_models import Investigation
from test_investigations import investigation_api,start,wait,AUTH


def test_git_metadata_symlink_rejected_before_any_config_read(investigation_api,tmp_path):
    *_,fixture,sha=investigation_api
    config=fixture/'.git/config'
    sentinel=tmp_path/'owned-sentinel.txt';sentinel.write_text('not Git configuration')
    config.unlink();config.symlink_to(sentinel)
    original=Path.read_text
    def guarded(path,*args,**kwargs):
        if path==config: raise AssertionError('Symlink target must never be opened')
        return original(path,*args,**kwargs)
    with patch.object(Path,'read_text',guarded):
        with pytest.raises(ValueError,match='symlinks'):
            RepositoryReader(fixture).git('status',['services/fixtures/faulty-commit.js'])


def test_nonregular_source_is_rejected_without_blocking(investigation_api):
    import os
    *_,fixture,sha=investigation_api
    path=fixture/'services/shared/not-source.js';os.mkfifo(path)
    with pytest.raises(ValueError):RepositoryReader(fixture).read('services/shared/not-source.js','payment-service')


def test_report_redaction_and_unverified_basename_rejection(investigation_api):
    client,*_=investigation_api
    job=wait(client,start(investigation_api));evidence=job['evidence']
    raw={key:job['report'][key] for key in AgentAnalysis.model_fields}
    raw['error_summary']='Observed failure; token=secret-sentinel-value'
    for malformed in (None,'not structured JSON',{'unexpected':'field'}):
        with pytest.raises(ValueError):validate_analysis(malformed,evidence,[])
    result=validate_analysis(raw,evidence,[])
    assert 'secret-sentinel-value' not in str(result)
    invalid=copy.deepcopy(raw)
    invalid['suspected_root_cause']['statement']='A failure was introduced in nonexistent-source.js.'
    with pytest.raises(ValueError,match='inline file'):validate_analysis(invalid,evidence,[])


def test_failed_runtime_probe_is_not_retried_by_polling():
    settings=Settings(agent_execution_enabled=True,agent_auth_token='test-only',agent_codex_api_key=SecretStr('test-only'),agent_codex_model='test-only-model')
    adapter=CodexAdapter(settings)
    with patch('app.codex_adapter.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='{"available":false}')) as run:
        assert not adapter.status()['available']
        adapter.checked=0
        assert not adapter.status()['available']
        assert run.call_count==1


def test_cancellation_and_source_audit_write_are_serialized(investigation_api):
    client,factory,worker,incident_id,*_=investigation_api
    with factory() as db:
        row=Investigation(id=str(uuid4()),incident_id=incident_id,service_name='payment-service',status='INSPECTING_CODE')
        db.add(row);db.commit();id=row.id
    paused=threading.Event();release=threading.Event();cancel_attempt=threading.Event();local=threading.local()
    engine=factory.kw['bind']
    def intercept(connection,cursor,statement,parameters,context,many):
        if getattr(local,'role',None)=='writer' and statement.startswith('UPDATE investigations'):
            paused.set()
            if not release.wait(4):raise AssertionError('Audit synchronization timeout')
        if getattr(local,'role',None)!='writer' and statement=='BEGIN IMMEDIATE':cancel_attempt.set()
    def write():
        local.role='writer';worker.update(id,'INSPECTING_CODE','Synthetic audit write')
    def cancel():
        local.role='cancel';return client.post(f'/api/investigations/{id}/cancel',headers=AUTH,json={})
    event.listen(engine,'before_cursor_execute',intercept)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            writer=pool.submit(write)
            assert paused.wait(3)
            cancellation=pool.submit(cancel)
            assert cancel_attempt.wait(3)
            release.set()
            writer.result(timeout=5)
            assert cancellation.result(timeout=5).status_code==200
        with factory() as db:assert db.get(Investigation,id).status=='CANCELLED'
        with pytest.raises(asyncio.CancelledError):worker.update(id,'ANALYZING_GIT','Must not resurrect')
    finally:
        release.set();event.remove(engine,'before_cursor_execute',intercept)


def test_remote_and_path_override_actions_rejected(investigation_api):
    from starlette.requests import Request
    from fastapi import HTTPException
    from app.investigations import authorize
    client,_,worker,incident_id,*_=investigation_api
    request=Request({'type':'http','client':('203.0.113.4',1234),'headers':[], 'app':client.app})
    with pytest.raises(HTTPException) as error:authorize(request,'Bearer '+worker.settings.agent_auth_token)
    assert error.value.status_code==403
    response=client.post(f'/api/incidents/{incident_id}/investigate',headers=AUTH,json={'authorize_paid_execution':True,'repository_root':'/unapproved'})
    assert response.status_code==422
