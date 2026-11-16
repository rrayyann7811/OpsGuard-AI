import asyncio
import copy
from pathlib import Path
import time
from uuid import uuid4
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.config import Settings
from app.database import Base,get_db
from app.models import Incident,now
from app.investigation_models import Investigation,InvestigationEvent,ACTIVE
from app.investigation_worker import InvestigationManager
from app.codex_adapter import CodexAdapter
from app.agent_evidence import RepositoryReader,bounded_command
from app.agent_reports import validate_analysis
from agent_support import TestAgent,git_fixture

ROOT=Path(__file__).resolve().parents[2]
TOKEN='local-investigation-test-token'
AUTH={'Authorization':'Bearer '+TOKEN}


class TestKnowledge:
    def search(self,query,**kwargs):
        return [{'incident':{'id':'SYN-PAY-004','root_cause':'Synthetic fee regression'},'similarity_score':.7,'source_ref':'synthetic test context'}]


@pytest.fixture
def investigation_api(tmp_path):
    fixture,sha=git_fixture(tmp_path/'fixture',ROOT)
    engine=create_engine('sqlite:///'+str(tmp_path/'jobs.db'),connect_args={'check_same_thread':False})
    factory=sessionmaker(bind=engine)
    settings=Settings(monitor_enabled=False,agent_project_root=str(fixture),agent_auth_token=TOKEN)
    def session():
        with factory() as db: yield db
    app.dependency_overrides[get_db]=session
    with patch('app.main.engine',engine),patch('app.main.settings',settings):
        with TestClient(app,client=('127.0.0.1',42000)) as client:
            worker=app.state.investigations
            worker.adapter=TestAgent();worker.knowledge=TestKnowledge()
            with factory() as db:
                row=Incident(id=str(uuid4()),service_name='payment-service',title='Fee invariant failure',severity='high',status='OPEN',
                    error_signature='fixture',error_type='CalculationRegression',error_message='Payment total violated fee invariant',stack_trace=None,
                    endpoint='/payments',http_status=500,first_seen=now(),last_seen=now(),occurrence_count=1)
                db.add(row);db.commit();id=row.id
            yield client,factory,worker,id,fixture,sha
    app.dependency_overrides.clear();engine.dispose()


def start(api):
    client,_,_,id,*_=api
    response=client.post(f'/api/incidents/{id}/investigate',headers=AUTH,json={'authorize_paid_execution':True})
    assert response.status_code==202,response.text
    return response.json()['investigation']['id']


def wait(client,id,timeout=8):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        row=client.get('/api/investigations/'+id).json()['investigation']
        if row['status'] in ('COMPLETED','FAILED','CANCELLED'): return row
        time.sleep(.02)
    raise AssertionError('Test investigation did not reach a terminal state')


def test_creation_persistent_events_report_and_evidence(investigation_api):
    client,factory,worker,incident_id,fixture,sha=investigation_api
    before={str(path.relative_to(fixture)):path.read_bytes() for path in fixture.rglob('*.js')}
    id=start(investigation_api);row=wait(client,id)
    assert row['status']=='COMPLETED',row
    assert row['execution_metadata']['mode']=='test-double'
    assert row['report']['confidence']['category']=='MEDIUM'
    assert 'TEST DOUBLE' in ' '.join(row['report']['limitations'])
    assert {'log','source','git','historical'} <= {evidence['kind'] for evidence in row['evidence']}
    assert any(item.get('commit_sha')==sha for item in row['evidence'])
    events=client.get(f'/api/investigations/{id}/events').json()['items']
    assert events[0]['status']=='QUEUED' and events[-1]['status']=='COMPLETED'
    assert all('Running one authorized Codex turn' not in item['message'] for item in events)
    assert any('TEST DOUBLE' in item['message'] for item in events)
    assert all(status in [event['status'] for event in events] for status in ACTIVE)
    assert client.get(f'/api/investigations/{id}/report').status_code==200
    assert client.get('/api/investigations/summary').json()['completed']==1
    assert client.get('/api/investigations?page_size=1').json()['total']==1
    with factory() as db:
        assert db.get(Incident,incident_id).status=='OPEN'
        assert db.get(Investigation,id).report is not None
    assert before=={str(path.relative_to(fixture)):path.read_bytes() for path in fixture.rglob('*.js')}


def test_auth_unavailable_and_validation(investigation_api):
    client,_,worker,id,*_=investigation_api
    path=f'/api/incidents/{id}/investigate'
    assert client.post(path,json={'authorize_paid_execution':True}).status_code==401
    assert client.post(path,headers=AUTH,json={'authorize_paid_execution':False}).status_code==422
    assert client.post(path,headers=AUTH,json={'authorize_paid_execution':True,'command':'rm'}).status_code==422
    worker.adapter=CodexAdapter(worker.settings)
    config=client.get('/api/investigations/configuration').json()
    assert config['available'] is False
    assert client.post(path,headers=AUTH,json={'authorize_paid_execution':True}).status_code==503
    assert client.get('/api/investigations?page=0').status_code==422
    assert client.get('/api/investigations/'+str(uuid4())).status_code==404


def test_duplicate_active_job_and_cancellation(investigation_api):
    class Blocking(TestAgent):
        async def run(self,bundle): await asyncio.Event().wait()
    client,_,worker,incident_id,*_=investigation_api
    worker.adapter=Blocking()
    id=start(investigation_api)
    response=client.post(f'/api/incidents/{incident_id}/investigate',headers=AUTH,json={'authorize_paid_execution':True})
    assert response.status_code==409
    assert client.get(f'/api/investigations/{id}/report').status_code==409
    assert client.post(f'/api/investigations/{id}/cancel',headers=AUTH,json={}).status_code==200
    assert wait(client,id)['status']=='CANCELLED'
    assert client.post(f'/api/investigations/{id}/cancel',headers=AUTH,json={}).status_code==409


def test_timeout_and_agent_error(investigation_api):
    class Broken(TestAgent):
        async def run(self,bundle): raise RuntimeError('secret-api-key')
    client,_,worker,*_=investigation_api
    worker.adapter=Broken();id=start(investigation_api);row=wait(client,id)
    assert row['status']=='FAILED' and 'secret-api-key' not in str(row)
    class Slow(TestAgent):
        async def run(self,bundle): await asyncio.sleep(10)
    worker.adapter=Slow();worker.settings=worker.settings.model_copy(update={'agent_timeout_seconds':.05})
    id=start(investigation_api);row=wait(client,id)
    assert row['status']=='FAILED' and row['error_code']=='TIMEOUT'


def test_missing_rag_and_git_are_explicit_not_fabricated(investigation_api,tmp_path):
    client,_,worker,*_=investigation_api
    import shutil
    bare=tmp_path/'no-git';shutil.copytree(worker.settings.agent_project_root,bare,ignore=shutil.ignore_patterns('.git'))
    worker.settings=worker.settings.model_copy(update={'agent_project_root':str(bare)})
    class Offline:
        def search(self,*args,**kwargs): raise RuntimeError('offline')
    worker.knowledge=Offline()
    row=wait(client,start(investigation_api))
    assert row['status']=='COMPLETED'
    limitations=' '.join(row['report']['limitations'])
    assert 'Git evidence unavailable' in limitations and 'Historical retrieval unavailable' in limitations
    assert not row['report']['suspected_commits']


def test_restart_recovery_never_completes_unfinished_jobs(investigation_api):
    _,factory,worker,incident_id,*_=investigation_api
    with factory() as db:
        row=Investigation(incident_id=incident_id,service_name='payment-service',status='QUEUED')
        db.add(row);db.commit();id=row.id
    replacement=InvestigationManager(worker.settings,factory,worker.knowledge,TestAgent())
    replacement.recover()
    with factory() as db:
        row=db.get(Investigation,id)
        assert row.status=='FAILED' and row.error_code=='BACKEND_RESTART' and row.report is None


def test_authorized_source_read_and_path_rejection(investigation_api,tmp_path):
    *_,fixture,sha=investigation_api
    reader=RepositoryReader(fixture)
    content,_=reader.read('services/fixtures/faulty-commit.js','payment-service')
    assert 'amount -' in content
    for path in ['../outside.js','/etc/passwd','services/.env','services/user-service/index.js','services/node_modules/secret.js']:
        with pytest.raises((ValueError,FileNotFoundError)): reader.read(path,'payment-service')
    secret=tmp_path/'outside.js';secret.write_text('secret')
    (fixture/'services/shared/escape.js').symlink_to(secret)
    with pytest.raises(ValueError): reader.read('services/shared/escape.js','payment-service')
    (fixture/'services/shared/link').symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises(ValueError): reader.read('services/shared/link/outside.js','payment-service')


def test_git_operation_command_path_and_hash_restrictions(investigation_api):
    *_,fixture,sha=investigation_api
    reader=RepositoryReader(fixture)
    paths=['services/fixtures/faulty-commit.js']
    for operation in ['log','show','diff','status']:
        code,text=reader.git(operation,paths,commit=sha if operation in ('show','diff') else None)
        assert code==0
    assert reader.git('blame',paths,line_range=(1,1))[0]==0
    for operation in ['commit','reset','push','checkout']:
        with pytest.raises(ValueError): reader.git(operation,paths)
    with pytest.raises(ValueError): reader.git('show',paths,commit='HEAD;touch bad')
    with pytest.raises(ValueError): reader.git('status',['services/.env'])
    assert RepositoryReader(ROOT).collect_git([])[1] # rejects inherited home Git


def test_report_rejects_fabricated_paths_lines_commits_and_citations(investigation_api):
    client,*_=investigation_api
    row=wait(client,start(investigation_api))
    report=row['report'];evidence=row['evidence']
    from app.agent_reports import AgentAnalysis
    raw={key:report[key] for key in AgentAnalysis.model_fields}
    # Stored historical refs have extra server-enriched fields; test uses no history in this double.
    for update in [
        lambda data:data['suspected_root_cause'].update(evidence_ids=['NONEXISTENT']),
        lambda data:data['affected_files'][0].update(path='private/credentials.js'),
        lambda data:data['affected_files'][0].update(end_line=99999),
        lambda data:data.update(suspected_commits=[{'commit_sha':'a'*40,'evidence_id':evidence[0]['id'],'explanation':'Invented commit'}]),
        lambda data:data['recommended_remediation'][0].update(statement='*** Begin Patch'),
    ]:
        invalid=copy.deepcopy(raw);update(invalid)
        with pytest.raises(ValueError):validate_analysis(invalid,evidence,[])
    raw['suspected_root_cause']['evidence_ids']=[next(item['id'] for item in evidence if item['kind']=='log')]
    assert validate_analysis(raw,evidence,[])['confidence']['category']=='INSUFFICIENT_EVIDENCE'


def test_bounded_command_timeout_and_output_size(tmp_path):
    import sys
    with pytest.raises(TimeoutError):bounded_command([sys.executable,'-c','import time;time.sleep(10)'],tmp_path,timeout=.05)
    with pytest.raises(ValueError):bounded_command([sys.executable,'-c','print("x"*10000)'],tmp_path,limit=100)


@pytest.mark.skipif(__import__('os').environ.get('OPSGUARD_LIVE_CODEX_TEST')!='I_AUTHORIZE_PAID_EXECUTION',reason='Real Codex execution requires separate explicit paid authorization and verified containment')
def test_opt_in_live_codex_is_never_replaced_with_double(investigation_api):
    client,_,worker,*_=investigation_api
    from app.config import get_settings
    worker.adapter=CodexAdapter(get_settings())
    assert worker.adapter.status()['available'],'Actual Codex credentials/configuration/containment unavailable'
    worker.knowledge=app.state.knowledge
    row=wait(client,start(investigation_api),timeout=worker.settings.agent_timeout_seconds+15)
    assert row['status']=='COMPLETED' and row['execution_metadata']['mode']=='live-codex'


def test_evaluation_refuses_mock_benchmark_and_handles_pending():
    from app.agent_evaluation import score
    assert score([],[])['root_cause_accuracy'] is None
    assert score([],[])['live_execution_performed'] is False
    with pytest.raises(ValueError):
        score([{'variant':'logs_git_rag','execution_mode':'test-double'}],[])


def test_invalid_transition_and_queue_limit(investigation_api):
    client,factory,worker,incident_id,*_=investigation_api
    with factory() as db:
        row=Investigation(incident_id=incident_id,service_name='payment-service',status='QUEUED')
        db.add(row);db.commit();id=row.id
    with pytest.raises(ValueError):worker.update(id,'GENERATING_REPORT','Illegal skipped stages')
    with factory() as db: assert db.get(Investigation,id).status=='QUEUED'
    worker.settings=worker.settings.model_copy(update={'agent_queue_limit':1})
    with factory() as db:
        other=Incident(id=str(uuid4()),service_name='user-service',title='Other',severity='high',status='OPEN',error_signature='other',
            error_type='TestError',error_message='Other failure',stack_trace=None,endpoint='/users',http_status=500,first_seen=now(),last_seen=now(),occurrence_count=1)
        db.add(other);db.commit();other_id=other.id
    response=client.post(f'/api/incidents/{other_id}/investigate',headers=AUTH,json={'authorize_paid_execution':True})
    assert response.status_code==429


def test_source_redaction_preserves_line_numbers(investigation_api):
    from app.agent_evidence import sanitize
    source='before\n-----BEGIN PRIVATE KEY-----\nsecret line\n-----END PRIVATE KEY-----\nafter\nconst token="secret-token";'
    clean=sanitize(source)
    assert clean.count('\n')==source.count('\n')
    assert 'secret line' not in clean and 'secret-token' not in clean
