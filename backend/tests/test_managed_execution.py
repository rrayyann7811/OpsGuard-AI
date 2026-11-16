"""Entirely offline. Contract coverage is the documented subset, not a live API test."""
import asyncio
import base64
import copy
import json
import socket
from typing import Literal
from unittest.mock import patch
import pytest
from pydantic import BaseModel, ConfigDict
from app.config import Settings
from app.evidence_export import EvidenceExportBuilder, ExportError, approval_digest
from app.execution_backends import create_adapter
from app.managed_codex_adapter import ManagedCodexAdapter, ManagedExecutionError
from app.test_double_adapter import deterministic_analysis


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError('Network forbidden in managed offline tests')
    monkeypatch.setattr(socket, 'create_connection', denied)
    monkeypatch.setattr(socket.socket, 'connect', denied)


@pytest.fixture
def bundle():
    return {'investigation_id': 'synthetic-job', 'incident_id': 'synthetic-incident',
            'service_name': 'payment-service', 'read_only': True, 'limitations': ['Synthetic fixture only'],
            'evidence': [
                {'id':'E001','kind':'log','content':'Synthetic failure; password="sentinel-value"\nat calculate (services/payment-service/index.js:2:1)'},
                {'id':'E002','kind':'source','path':'services/payment-service/index.js','start_line':1,'end_line':2,
                 'sha256':'a'*64,'content':'const total = 1;\nthrow Error("synthetic");'},
                {'id':'E003','kind':'git','operation':'diff','commit_sha':'b'*40,
                 'content':'diff --git a/services/payment-service/index.js b/services/payment-service/index.js\n- old\n+ synthetic'},
                {'id':'E004','kind':'historical','historical_id':'SYN-PAY-004','similarity_score':.7,
                 'source_ref':'synthetic history','content':'Synthetic fee issue'}]}


def settings(bundle, **updates):
    return Settings(_env_file=None, agent_execution_enabled=True, agent_managed_enabled=True,
                    agent_auth_token='offline-local-token', agent_managed_model='offline-contract-model',
                    agent_managed_synthetic_digests=[approval_digest(bundle)], **updates)


class FakeClient:
    is_test_double = True

    def __init__(self, bundle):
        self.bundle, self.calls = bundle, []
        self.sequence = 0
        self.error = None
        self.block = False
        self.cleanup_error = False
        self.output = None
        self.event = None

    async def create(self, request):
        self.calls.append(('create', request))
        if self.error == 'create': raise RuntimeError('secret-provider-error')
        self.sequence += 1
        return {'id': f'sess_offline_{self.sequence}'}

    async def observe(self, session_id):
        self.calls.append(('observe', session_id))
        if self.event: self.event.set()
        if self.block: await asyncio.Event().wait()
        if self.error == 'observe': raise RuntimeError('secret-provider-error')
        return {'terminal_event':'agent.session.turn.completed'}

    async def result(self, session_id, max_bytes):
        self.calls.append(('result', session_id, max_bytes))
        return {'output_text': self.output if self.output is not None else json.dumps(deterministic_analysis(self.bundle)),
                'usage': {'input_tokens':10, 'output_tokens':20, 'total_tokens':30}}

    async def events(self, session_id, request):
        self.calls.append(('events', session_id, request))

    async def delete(self, session_id):
        self.calls.append(('delete', session_id))
        if self.cleanup_error: raise RuntimeError('private provider detail')


# https://developers.openai.com/api/reference/resources/beta/subresources/agents/subresources/sessions/methods/create
# Typed contract subset transcribed from the official create-session reference linked
# in docs/MANAGED_AGENT_EXECUTION_PLAN.md, reviewed offline (no schema/URL fetching).
class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Format(Contract):
    type: Literal['json_schema']
    schema_: dict = __import__('pydantic').Field(alias='schema')


class Text(Contract):
    format: Format


class Delegation(Contract):
    enabled: Literal[False]


class Agent(Contract):
    model: str
    instructions: str
    tools: list
    multi_agent: Delegation
    text: Text


class Network(Contract):
    access: Literal['disabled']


class InlineFile(Contract):
    type: Literal['inline']
    path: Literal['/workspace/inputs/evidence.json']
    data: str


class Environment(Contract):
    type: Literal['openai_hosted']
    container_size: Literal['small']
    network: Network
    files: list[InlineFile]


class SessionRequest(Contract):
    agent: Agent
    environment: Environment
    input: str
    stream: Literal[False]


def test_backend_selection_and_defaults():
    for backend, name in [('local-codex','CodexAdapter'),('managed-codex','ManagedCodexAdapter'),('test-double','DeterministicAdapter')]:
        adapter=create_adapter(Settings(_env_file=None,agent_execution_backend=backend))
        assert type(adapter).__name__ == name
        assert not adapter.status()['available']
    with pytest.raises(ValueError): Settings(_env_file=None,agent_execution_backend='fallback')
    with pytest.raises(ValueError): Settings(_env_file=None,agent_managed_max_investigations_per_session=2)
    assert Settings(_env_file=None).agent_managed_enabled is False


def test_no_live_transport_even_with_enabled_flags(bundle):
    adapter=ManagedCodexAdapter(settings(bundle))
    assert not adapter.status()['available'] and not adapter.status()['live_available']
    with pytest.raises(ManagedExecutionError): asyncio.run(adapter.run(bundle,authorized=True,journal=lambda x:None))
    class Real(FakeClient): is_test_double=False
    assert not ManagedCodexAdapter(settings(bundle), Real(bundle)).status()['available']
    with pytest.raises(ValueError): ManagedCodexAdapter(settings(bundle),requested_permissions={'full-host'})


def test_export_deterministic_redaction_and_provenance(bundle):
    original=copy.deepcopy(bundle)
    builder=EvidenceExportBuilder([approval_digest(bundle)])
    output=builder.build(bundle)
    assert output==builder.build(bundle) and original==bundle
    assert 'sentinel-value' not in json.dumps(output)
    assert output['evidence'][1]['sha256']=='a'*64
    assert len(output['evidence'][1]['export_sha256'])==64
    assert [x['id'] for x in output['evidence']]==['E001','E002','E003','E004']
    bundle['evidence'][0]['content']='different'
    with pytest.raises(ExportError,match='approval'): builder.build(bundle)


@pytest.mark.parametrize('path',['/Users/private.js','../secret.js','services/.env','services/payment-service/.env.js',
                               'services/user-service/index.js','services/payment-service/node_modules/key.js',
                               'services/payment-service/index.py','services/payment-service/../shared/index.js',
                               'services/payment-service//index.js'])
def test_reject_unauthorized_files_without_reading(bundle,path):
    bundle['evidence'][1]['path']=path
    with patch('builtins.open',side_effect=AssertionError('Exporter must never read paths')):
        with pytest.raises(ValueError): EvidenceExportBuilder([approval_digest(bundle)]).build(bundle)


@pytest.mark.parametrize('content',['AKIAABCDEFGHIJKLMNOP','ghp_privatecanary123','/Users/private/file',
                                  'https://internal.example.invalid/incident','file .env credentials'])
def test_residual_sensitive_content_rejected(bundle,content):
    bundle['evidence'][0]['content']=content
    with pytest.raises(ExportError): EvidenceExportBuilder([approval_digest(bundle)]).build(bundle)


def test_payload_bounds_duplicate_ids_and_fields(bundle):
    for change in [lambda b:b.update(unsafe=True),lambda b:b['evidence'][0].update(credentials='secret'),
                   lambda b:b['evidence'][1].update(id='E001'),lambda b:b.update(read_only=False),
                   lambda b:b['evidence'][2].update(content='diff --git a/services/.env b/services/.env')]:
        invalid=copy.deepcopy(bundle);change(invalid)
        with pytest.raises(ValueError): EvidenceExportBuilder([approval_digest(invalid)]).build(invalid)
    bundle['evidence'][0]['content']='界'*500
    with pytest.raises(ExportError,match='byte limit'): EvidenceExportBuilder([approval_digest(bundle)],1024).build(bundle)
    with pytest.raises(ExportError): EvidenceExportBuilder().build(bundle)


def test_session_contract_lifecycle_and_provenance(bundle):
    client=FakeClient(bundle);adapter=ManagedCodexAdapter(settings(bundle),client);journal=[]
    result=asyncio.run(adapter.run(bundle,authorized=True,journal=journal.append))
    assert result['metadata']['mode']=='test-double' and result['metadata']['backend']=='managed-codex'
    assert result['metadata']['usage']['total_tokens']==30
    assert 'TEST DOUBLE' in ' '.join(result['analysis']['limitations'])
    assert journal[-1]['cleanup_state']=='deleted'
    assert [x[0] for x in client.calls]==['create','observe','result','delete']
    request=SessionRequest.model_validate(client.calls[0][1])
    assert request.agent.tools==[] and request.environment.network.access=='disabled'
    data=json.loads(base64.b64decode(request.environment.files[0].data))
    assert data['schema_version']=='opsguard.synthetic-export.v1'
    assert not any(k in client.calls[0][1] for k in ['api_key','max_cost','sandboxMode'])
    assert journal[0]['cleanup_state']=='creating' and journal[1]['session_id'].startswith('sess_')
    # Each investigation gets its own session; never submit a second turn into one session.
    asyncio.run(adapter.run(bundle,authorized=True,journal=journal.append))
    assert client.sequence==2


def test_authorization_and_journal_required(bundle):
    client=FakeClient(bundle);adapter=ManagedCodexAdapter(settings(bundle),client)
    for kwargs in [{},{'authorized':True},{'authorized':False,'journal':lambda x:None}]:
        with pytest.raises(ManagedExecutionError):asyncio.run(adapter.run(bundle,**kwargs))
    assert client.calls==[]
    disabled=ManagedCodexAdapter(settings(bundle).model_copy(update={'agent_managed_enabled':False}),client)
    with pytest.raises(ManagedExecutionError):asyncio.run(disabled.run(bundle,authorized=True,journal=lambda x:None))


@pytest.mark.parametrize('output',['not-json','{}','{"provider":"real"}',json.dumps({'output':'x'*140000})])
def test_malformed_report_and_output_limits(bundle,output):
    client=FakeClient(bundle);client.output=output;journal=[]
    with pytest.raises(ManagedExecutionError):asyncio.run(ManagedCodexAdapter(settings(bundle),client).run(bundle,authorized=True,journal=journal.append))
    assert [x[0] for x in client.calls][-2:]==['events','delete']
    assert client.calls[-2][2]=={'events':[{'type':'agent.session.input.cancel'}]}


def test_fabricated_report_citations_rejected(bundle):
    client=FakeClient(bundle);raw=deterministic_analysis(bundle)
    raw['suspected_root_cause']['evidence_ids']=['E999'];client.output=json.dumps(raw)
    with pytest.raises(ManagedExecutionError):asyncio.run(ManagedCodexAdapter(settings(bundle),client).run(bundle,authorized=True,journal=lambda x:None))


@pytest.mark.parametrize('stage',['create','observe'])
def test_remote_failure_no_retry_or_secret_disclosure(bundle,stage):
    client=FakeClient(bundle);client.error=stage;adapter=ManagedCodexAdapter(settings(bundle),client);journal=[]
    with pytest.raises(ManagedExecutionError) as error:asyncio.run(adapter.run(bundle,authorized=True,journal=journal.append))
    assert 'secret' not in str(error.value)+str(journal)
    assert sum(x[0]=='create' for x in client.calls)==1
    if stage=='create':
        assert not adapter.status()['available']
        assert any(x.get('cleanup_state')=='unknown' for x in journal)
    else:assert client.calls[-1][0]=='delete'


def test_cleanup_failure_blocks_new_work(bundle):
    client=FakeClient(bundle);client.cleanup_error=True;adapter=ManagedCodexAdapter(settings(bundle),client);journal=[]
    with pytest.raises(ManagedExecutionError,match='CLEANUP_PENDING'):asyncio.run(adapter.run(bundle,authorized=True,journal=journal.append))
    assert not adapter.status()['available'] and journal[-1]['cleanup_state']=='pending'


def test_timeout_cancel_and_concurrency(bundle):
    async def scenario(cancel):
        client=FakeClient(bundle);client.block=True;client.event=asyncio.Event();journal=[]
        adapter=ManagedCodexAdapter(settings(bundle,agent_managed_duration_seconds=.02),client)
        task=asyncio.create_task(adapter.run(bundle,authorized=True,journal=journal.append))
        await client.event.wait()
        with pytest.raises(ManagedExecutionError,match='CONCURRENCY'):await adapter.run(bundle,authorized=True,journal=journal.append)
        if cancel:task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else TimeoutError):await task
        assert client.calls[-2][0]=='events' and client.calls[-1][0]=='delete'
        assert adapter._active==0 and journal[-1]['cleanup_state']=='deleted'
    asyncio.run(scenario(False));asyncio.run(scenario(True))


def test_restart_reconciliation_never_submits_work(bundle):
    async def scenario():
        client=FakeClient(bundle);adapter=ManagedCodexAdapter(settings(bundle),client);journal=[]
        await adapter.reconcile({'session_id':'sess_offline_old','cleanup_state':'active'},journal.append)
        assert [x[0] for x in client.calls]==['events','delete']
        await adapter.reconcile({'cleanup_state':'creating'},journal.append)
        assert not adapter.status()['available'] and journal[-1]['cleanup_state']=='unknown'
    asyncio.run(scenario())

# Exercise the unchanged HTTP/SQLite/collector/report path using owned synthetic fixtures.
from test_investigations import investigation_api, start, wait, AUTH
from app.investigation_worker import InvestigationManager
from app.investigation_models import Investigation


def managed_worker_fixture(api, bundle):
    client, factory, worker, incident_id, *_ = api
    # Use a wholly authored source fixture; copied service code contains internal URLs
    # which the export gate intentionally rejects.
    from pathlib import Path
    synthetic=Path(worker.settings.agent_project_root)/'managed-synthetic'
    source=synthetic/'services/payment-service/index.js'
    source.parent.mkdir(parents=True,exist_ok=True)
    source.write_text('const total = 1;\nthrow Error("Synthetic failure");\n')
    worker.settings=worker.settings.model_copy(update={'agent_project_root':str(synthetic)})
    fake=FakeClient(bundle)
    configured=settings(bundle).model_copy(update={'agent_auth_token':worker.settings.agent_auth_token})
    adapter=ManagedCodexAdapter(configured,fake)
    original_build=adapter.exporter.build
    def approve_owned_fixture(collected):
        # Test-only operator review: this fixture's incident and collector inputs are synthetic.
        assert collected['incident_id']==incident_id
        adapter.exporter.approved=frozenset({approval_digest(collected)})
        return original_build(collected)
    adapter.exporter.build=approve_owned_fixture
    worker.adapter=adapter
    return fake,adapter


def test_managed_http_report_and_durable_cleanup(investigation_api,bundle):
    client,factory,worker,incident_id,*_=investigation_api
    fake,adapter=managed_worker_fixture(investigation_api,bundle)
    row=wait(client,start(investigation_api))
    assert row['status']=='COMPLETED',row
    assert row['execution_metadata']['backend']=='managed-codex'
    assert row['execution_metadata']['mode']=='test-double'
    assert row['execution_metadata']['cleanup_state']=='deleted'
    assert row['execution_metadata']['execution_authorized'] is True
    assert row['execution_metadata']['session_id']=='sess_offline_1'
    assert row['report']['execution_mode']=='test-double'
    assert any('TEST DOUBLE' in x for x in row['report']['limitations'])
    assert not any('secret-provider-error' in str(x) for x in row.values())


def test_managed_duplicate_cancel_and_failure_persistence(investigation_api,bundle):
    import time
    client,_,worker,incident_id,*_=investigation_api
    fake,adapter=managed_worker_fixture(investigation_api,bundle);fake.block=True
    id=start(investigation_api)
    for _ in range(200):
        row=client.get('/api/investigations/'+id).json()['investigation']
        if row['execution_metadata'].get('session_id'):break
        time.sleep(.01)
    assert row['execution_metadata'].get('session_id')
    assert client.post(f'/api/incidents/{incident_id}/investigate',headers=AUTH,json={'authorize_paid_execution':True}).status_code==409
    assert client.post(f'/api/investigations/{id}/cancel',headers=AUTH).status_code==200
    for _ in range(200):
        row=client.get('/api/investigations/'+id).json()['investigation']
        if row['execution_metadata'].get('cleanup_state')=='deleted':break
        time.sleep(.01)
    assert row['status']=='CANCELLED' and row['report'] is None
    assert row['execution_metadata']['cleanup_state']=='deleted'
    fake.block=False;fake.output='malformed'
    row=wait(client,start(investigation_api))
    assert row['status']=='FAILED' and row['report'] is None
    assert row['execution_metadata']['remote_error_code']=='MANAGED_EXECUTION_FAILED'
    assert row['execution_metadata']['cleanup_state']=='deleted'


def test_worker_restart_recovers_remote_ids_without_new_turn(investigation_api,bundle):
    from uuid import uuid4
    _,factory,worker,incident_id,*_=investigation_api
    fake=FakeClient(bundle);adapter=ManagedCodexAdapter(settings(bundle),fake)
    with factory() as db:
        row=Investigation(id=str(uuid4()),incident_id=incident_id,service_name='payment-service',status='GENERATING_REPORT',
                          execution_metadata={'backend':'managed-codex','mode':'test-double',
                                              'session_id':'sess_offline_old','cleanup_state':'active'})
        db.add(row);db.commit();id=row.id
    async def restart():
        replacement=InvestigationManager(worker.settings,factory,worker.knowledge,adapter)
        replacement.start()
        await asyncio.sleep(.03)
        await replacement.stop()
    asyncio.run(restart())
    with factory() as db:
        row=db.get(Investigation,id)
        assert row.status=='FAILED' and row.error_code=='BACKEND_RESTART' and row.report is None
        assert row.execution_metadata['session_id']=='sess_offline_old'
        assert row.execution_metadata['cleanup_state']=='deleted'
    assert [x[0] for x in fake.calls]==['events','delete']


def test_idle_poll_is_not_completion_and_actions_are_rejected(bundle):
    class Polling(FakeClient):
        async def observe(self,id):
            self.calls.append(('observe',id))
            count=sum(x[0]=='observe' for x in self.calls)
            return {} if count==1 else {'terminal_event':'agent.session.turn.completed'}
    fake=Polling(bundle)
    result=asyncio.run(ManagedCodexAdapter(settings(bundle),fake).run(bundle,authorized=True,journal=lambda x:None))
    assert result['metadata']['mode']=='test-double'
    assert sum(x[0]=='observe' for x in fake.calls)==2
    class Action(FakeClient):
        async def observe(self,id):return {'requires_action':True}
    fake=Action(bundle)
    with pytest.raises(ManagedExecutionError,match='UNSUPPORTED_REMOTE_ACTION'):
        asyncio.run(ManagedCodexAdapter(settings(bundle),fake).run(bundle,authorized=True,journal=lambda x:None))
    assert fake.calls[-2][0]=='events' and fake.calls[-1][0]=='delete'


def test_cleanup_deadline_is_persisted_and_blocks_new_sessions(bundle):
    class Hanging(FakeClient):
        async def delete(self,id):
            self.calls.append(('delete',id))
            await asyncio.Event().wait()
    fake=Hanging(bundle);journal=[]
    adapter=ManagedCodexAdapter(settings(bundle,agent_managed_cleanup_seconds=.01),fake)
    with pytest.raises(ManagedExecutionError,match='CLEANUP_PENDING'):
        asyncio.run(adapter.run(bundle,authorized=True,journal=journal.append))
    assert journal[-1]['cleanup_state']=='pending' and adapter._active==0
    assert not adapter.status()['available']


def test_explicit_test_double_backend_through_existing_api(investigation_api):
    client,_,worker,*_=investigation_api
    configured=worker.settings.model_copy(update={'agent_execution_backend':'test-double','agent_execution_enabled':True})
    worker.adapter=create_adapter(configured)
    row=wait(client,start(investigation_api))
    assert row['status']=='COMPLETED'
    assert row['execution_metadata']['backend']=='test-double'
    assert row['execution_metadata']['mode']=='test-double'
    assert 'TEST DOUBLE' in row['report']['suspected_root_cause']['statement']


def test_failed_persistence_after_creation_still_cleans_up(bundle):
    fake=FakeClient(bundle);journal=[]
    def broken(changes):
        journal.append(changes)
        if changes.get('cleanup_state')=='active':raise RuntimeError('DB journal unavailable')
    with pytest.raises(ManagedExecutionError):
        asyncio.run(ManagedCodexAdapter(settings(bundle),fake).run(bundle,authorized=True,journal=broken))
    assert fake.calls[-2][0]=='events' and fake.calls[-1][0]=='delete'
    assert not any(x[0]=='result' for x in fake.calls)


def test_database_failure_cannot_prevent_known_session_cleanup(bundle):
    fake=FakeClient(bundle);adapter=ManagedCodexAdapter(settings(bundle),fake)
    def broken(changes):
        if fake.sequence:raise RuntimeError('database down')
    with pytest.raises(RuntimeError):asyncio.run(adapter.run(bundle,authorized=True,journal=broken))
    assert fake.calls[-2][0]=='events' and fake.calls[-1][0]=='delete'
    assert not adapter.status()['available']


def test_secret_redaction_and_sanitized_expansion_bound(bundle):
    from app.evidence_export import encoded
    original=copy.deepcopy(bundle)
    bundle['evidence'][0]['content']='Bearer synthetic-credential\n-----BEGIN PRIVATE KEY-----\nsynthetic-private-value\n-----END PRIVATE KEY-----\nfixture@example.invalid'
    exported=EvidenceExportBuilder([approval_digest(bundle)]).build(bundle)
    text=exported['evidence'][0]['content']
    assert not any(value in text for value in ['synthetic-credential','synthetic-private-value','fixture@example.invalid'])
    assert text.count('\n')==bundle['evidence'][0]['content'].count('\n')
    with pytest.raises(ExportError,match='Sanitized export'):
        EvidenceExportBuilder([approval_digest(original)],len(encoded(original))).build(original)
