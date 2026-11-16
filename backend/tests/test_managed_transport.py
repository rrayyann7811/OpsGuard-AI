"""Real HTTP serialization/parsing via MockTransport only; socket creation is denied."""
import asyncio
import base64
import copy
import json
import socket
import httpx
import pytest
from app.config import Settings
from app.agent_reports import AgentAnalysis
from app.evidence_export import approval_digest
from app.execution_backends import create_adapter
from app.managed_api_transport import ManagedAgentsHTTPClient, ProviderError
from app.managed_codex_adapter import ManagedCodexAdapter, ManagedExecutionError
from app.test_double_adapter import deterministic_analysis

SID='sess_mock_only'
TID='turn_mock_only'
USAGE={'input_tokens':10,'output_tokens':7,'total_tokens':17,
       'input_tokens_details':{'cached_tokens':3},'output_tokens_details':{'reasoning_tokens':2}}


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def denied(*args,**kwargs): raise AssertionError('Real sockets forbidden')
    monkeypatch.setattr(socket.socket,'connect',denied)
    monkeypatch.setattr(socket,'create_connection',denied)


@pytest.fixture
def bundle():
    return {'investigation_id':'synthetic-job','incident_id':'synthetic-incident','service_name':'payment-service',
            'read_only':True,'limitations':['Synthetic fixture'],
            'evidence':[{'kind':'log','id':'E001','content':'Synthetic timeout observed'}]}


def configuration(bundle,**updates):
    values=dict(agent_execution_enabled=True,agent_managed_enabled=True,agent_auth_token='mock-local-auth',
                agent_managed_http_enabled=True,agent_managed_model='mock-contract-model',
                agent_managed_synthetic_digests=[approval_digest(bundle)],agent_managed_retry_delay_seconds=0)
    values.update(updates)
    return Settings(_env_file=None,**values)


def request_body(bundle):
    from app.evidence_export import EvidenceExportBuilder,encoded
    export=EvidenceExportBuilder([approval_digest(bundle)]).build(bundle)
    return {'agent':{'model':'mock-contract-model','instructions':'Analyze synthetic input',
                     'tools':[],'multi_agent':{'enabled':False},
                     'text':{'format':{'type':'json_schema','schema':AgentAnalysis.model_json_schema()}}},
            'environment':{'type':'openai_hosted','container_size':'small','network':{'access':'disabled'},
                           'files':[{'type':'inline','path':'/workspace/inputs/evidence.json',
                                     'data':base64.b64encode(encoded(export)).decode()}]},
            'input':'Analyze synthetic evidence','stream':False}


def session(status='idle',**extra):
    return {'id':SID,'object':'agent.session','status':status,'required_actions':[],'error':None,'usage':USAGE,**extra}


def turn(status='completed',**extra):
    return {'id':TID,'object':'agent.session.turn','session_id':SID,'subagent_id':None,
            'status':status,'usage':USAGE,'error':None,**extra}


def page(items,**extra):
    return {'object':'list','data':items,'has_more':False,'last_id':None,**extra}


def message(text,**extra):
    return {'id':'msg_mock','type':'message','role':'assistant','phase':'final_answer','status':'completed',
            'turn_id':TID,'content':[{'type':'output_text','text':text}],**extra}


class Provider:
    """Wire fixtures mirror the official beta session/turn/item/delete contract."""
    def __init__(self,bundle):
        self.bundle=bundle;self.calls=[];self.status='completed';self.session_status='idle'
        self.turns=[];self.items=None;self.fail_delete=False

    async def __call__(self,request):
        self.calls.append(request)
        assert request.url.host=='api.openai.com'
        assert request.headers['OpenAI-Beta']=='agents=v1'
        assert request.headers['Authorization']=='Bearer mock-only-not-a-credential'
        path=request.url.path
        if request.method=='POST' and path=='/v1/agents/sessions':return httpx.Response(201,json=session())
        if request.method=='POST' and path.endswith('/events'):return httpx.Response(202)
        if request.method=='DELETE':
            if self.fail_delete:return httpx.Response(409,json={'error':{'code':'conflict','message':'private text'}})
            return httpx.Response(200,json={'id':SID,'object':'agent.session.deleted','deleted':True})
        if path.endswith('/turns'):
            status=self.turns.pop(0) if self.turns else self.status
            return httpx.Response(200,json=page([] if status is None else [turn(status)]))
        if path.endswith('/items'):
            items=self.items if self.items is not None else [message(json.dumps(deterministic_analysis(self.bundle)))]
            return httpx.Response(200,json=page(items))
        return httpx.Response(200,json=session(self.session_status))


async def exercise(bundle,handler,**updates):
    settings=configuration(bundle,**updates)
    client=ManagedAgentsHTTPClient(settings,transport=httpx.MockTransport(handler),authorized=True)
    adapter=ManagedCodexAdapter(settings,client);journal=[]
    try:
        return await adapter.run(bundle,authorized=True,journal=journal.append),journal,client
    finally:await client.aclose()


def test_http_lifecycle_contract_and_usage(bundle):
    provider=Provider(bundle)
    result,journal,client=asyncio.run(exercise(bundle,provider))
    assert result['metadata']['mode']=='test-double'
    assert result['metadata']['usage']==USAGE
    assert any(x.get('usage')==USAGE for x in journal)
    assert any(x.get('cleanup_state')=='deleted' for x in journal)
    assert journal[-1]['http_request_count']==5
    assert [(r.method,r.url.path) for r in provider.calls]==[
        ('POST','/v1/agents/sessions'),('GET',f'/v1/agents/sessions/{SID}'),
        ('GET',f'/v1/agents/sessions/{SID}/turns'),('GET',f'/v1/agents/sessions/{SID}/items'),
        ('DELETE',f'/v1/agents/sessions/{SID}')]
    body=json.loads(provider.calls[0].content)
    assert body['environment']['network']=={'access':'disabled'}
    assert body['agent']['text']['format']['schema']==AgentAnalysis.model_json_schema()
    assert not any(k in body for k in ['max_cost','api_key','read_only'])
    assert json.loads(base64.b64decode(body['environment']['files'][0]['data']))['evidence'][0]['id']=='E001'


@pytest.mark.parametrize('status,code',[(400,'INVALID_REQUEST'),(401,'AUTHENTICATION'),(403,'PERMISSION'),
                                      (429,'RATE_LIMIT'),(500,'UNAVAILABLE'),(503,'UNAVAILABLE')])
def test_creation_errors_never_retry_or_leak(bundle,caplog,status,code):
    calls=[]
    async def handler(req):
        calls.append(req)
        return httpx.Response(status,json={'error':{'code':'secret-code-value','message':'secret-body-value'}})
    async def scenario():
        client=ManagedAgentsHTTPClient(configuration(bundle),transport=httpx.MockTransport(handler),authorized=True)
        try:
            with pytest.raises(ProviderError,match=code):await client.create(request_body(bundle))
            with pytest.raises(ProviderError):await client.create(request_body(bundle))
        finally:await client.aclose()
    asyncio.run(scenario())
    assert len(calls)==1 and 'secret-body-value' not in caplog.text and 'secret-code-value' not in caplog.text


def test_disabled_transport_and_real_clients_are_never_eligible(bundle):
    async def scenario():
        for settings,transport,authorized in [
            (configuration(bundle,agent_managed_http_enabled=False),httpx.MockTransport(lambda r:pytest.fail('HTTP')),True),
            (configuration(bundle),httpx.MockTransport(lambda r:pytest.fail('HTTP')),False),
            (configuration(bundle),None,True),
            (configuration(bundle),httpx.AsyncHTTPTransport(),True)]:
            client=ManagedAgentsHTTPClient(settings,transport=transport,authorized=authorized)
            try:
                assert not ManagedCodexAdapter(settings,client).status()['available']
                with pytest.raises(ProviderError,match='NOT_AUTHORIZED'):await client.create(request_body(bundle))
            finally:await client.aclose()
        with pytest.raises(ValueError):configuration(bundle,agent_managed_max_concurrent_sessions=2)
    asyncio.run(scenario())
    configured=configuration(bundle,agent_execution_backend='managed-codex')
    assert not create_adapter(configured).status()['available']


@pytest.mark.parametrize('change',[
    lambda x:x.update(api_key='not-authorized'),lambda x:x['environment']['network'].update(access='enabled'),
    lambda x:x['environment']['files'][0].update(path='/etc/private'),lambda x:x['agent']['text']['format'].update(schema={}),
    lambda x:x.update(stream=True),lambda x:x['agent']['multi_agent'].update(enabled=True)])
def test_invalid_request_rejected_before_http(bundle,change):
    body=request_body(bundle);change(body)
    async def scenario():
        client=ManagedAgentsHTTPClient(configuration(bundle),transport=httpx.MockTransport(lambda r:pytest.fail('HTTP')),authorized=True)
        try:
            with pytest.raises(ProviderError,match='INVALID_MANAGED_REQUEST'):await client.create(body)
        finally:await client.aclose()
    asyncio.run(scenario())


def test_idle_polling_is_not_completion(bundle):
    provider=Provider(bundle);provider.turns=[None,'in_progress','completed']
    result,journal,_=asyncio.run(exercise(bundle,provider))
    assert result['metadata']['mode']=='test-double'
    assert sum(r.url.path.endswith('/turns') for r in provider.calls)==3


@pytest.mark.parametrize('status',['failed','cancelled','waiting'])
def test_unsuccessful_turns_cancel_and_cleanup(bundle,status):
    provider=Provider(bundle);provider.status=status
    async def scenario():
        client=ManagedAgentsHTTPClient(configuration(bundle),transport=httpx.MockTransport(provider),authorized=True)
        adapter=ManagedCodexAdapter(configuration(bundle),client);journal=[]
        try:
            with pytest.raises(ManagedExecutionError):await adapter.run(bundle,authorized=True,journal=journal.append)
            assert any(x.get('usage')==USAGE for x in journal) if status!='waiting' else True
            assert any(x.get('cleanup_state')=='deleted' for x in journal)
        finally:await client.aclose()
    asyncio.run(scenario())
    assert provider.calls[-2].url.path.endswith('/events') and provider.calls[-1].method=='DELETE'
    assert json.loads(provider.calls[-2].content)=={'events':[{'type':'agent.session.input.cancel'}]}


def test_failed_session_and_required_action(bundle):
    async def scenario(status):
        provider=Provider(bundle);provider.session_status=status
        with pytest.raises(ManagedExecutionError):await exercise(bundle,provider)
        assert not any(r.url.path.endswith('/items') for r in provider.calls)
        assert provider.calls[-1].method=='DELETE'
    asyncio.run(scenario('failed'));asyncio.run(scenario('requires_action'))


@pytest.mark.parametrize('status',[429,500,503])
def test_idempotent_read_retries_bounded(bundle,status):
    provider=Provider(bundle);attempts=0
    async def handler(req):
        nonlocal attempts
        if req.method=='GET' and req.url.path.endswith(SID):
            attempts+=1
            if attempts==1:return httpx.Response(status,headers={'retry-after':'0'},json={'error':{'message':'secret'}})
        return await provider(req)
    result,_,_=asyncio.run(exercise(bundle,handler))
    assert result['metadata']['mode']=='test-double' and attempts==2


def test_retry_exhaustion_and_retry_after_bounds(bundle):
    for header,code in [('0','RATE_LIMIT'),('9999','RETRY_AFTER_EXCEEDS_LIMIT'),('nan','RETRY_AFTER_EXCEEDS_LIMIT')]:
        provider=Provider(bundle);reads=[]
        async def handler(req):
            if req.method=='GET':
                reads.append(req);return httpx.Response(429,headers={'retry-after':header},json={'error':{'message':'do not log'}})
            return await provider(req)
        with pytest.raises(ManagedExecutionError,match=code):asyncio.run(exercise(bundle,handler))
        assert len(reads)==(2 if header=='0' else 1)


def test_timeout_and_unavailable_create_are_ambiguous_not_retried(bundle):
    async def scenario(error):
        calls=[]
        async def handler(req):
            calls.append(req)
            if error=='slow':await asyncio.sleep(1)
            else:raise httpx.ConnectError('secret connection detail',request=req)
        client=ManagedAgentsHTTPClient(configuration(bundle,agent_managed_request_timeout_seconds=.01),transport=httpx.MockTransport(handler),authorized=True)
        adapter=ManagedCodexAdapter(configuration(bundle),client);journal=[]
        try:
            with pytest.raises(ManagedExecutionError):await adapter.run(bundle,authorized=True,journal=journal.append)
            assert len(calls)==1 and not adapter.status()['available']
            assert any(x.get('cleanup_state')=='unknown' for x in journal)
        finally:await client.aclose()
    asyncio.run(scenario('slow'));asyncio.run(scenario('connection'))


def test_cleanup_failure_is_pending_and_blocks_admission(bundle):
    provider=Provider(bundle);provider.fail_delete=True
    async def scenario():
        client=ManagedAgentsHTTPClient(configuration(bundle),transport=httpx.MockTransport(provider),authorized=True)
        adapter=ManagedCodexAdapter(configuration(bundle),client);journal=[]
        try:
            with pytest.raises(ManagedExecutionError,match='CLEANUP_PENDING'):
                await adapter.run(bundle,authorized=True,journal=journal.append)
            assert any(x.get('cleanup_state')=='pending' for x in journal)
            assert not adapter.status()['available']
        finally:await client.aclose()
    asyncio.run(scenario())
    assert sum(r.method=='DELETE' for r in provider.calls)==2


@pytest.mark.parametrize('bad',[{}, {'id':SID,'object':'agent.session','status':'completed'},
                             {'id':'../escape','object':'agent.session','status':'idle'},
                             {'id':SID,'object':'agent.session','status':'idle','usage':{'input_tokens':-1}}])
def test_malformed_create_responses(bundle,bad):
    async def scenario():
        client=ManagedAgentsHTTPClient(configuration(bundle),transport=httpx.MockTransport(lambda r:httpx.Response(201,json=bad)),authorized=True)
        try:
            with pytest.raises(ProviderError,match='MALFORMED'):await client.create(request_body(bundle))
        finally:await client.aclose()
    asyncio.run(scenario())


def test_non_json_redirect_and_response_limits(bundle):
    async def scenario(response,settings,code):
        client=ManagedAgentsHTTPClient(settings,transport=httpx.MockTransport(lambda r:response),authorized=True)
        try:
            with pytest.raises(ProviderError,match=code):await client.create(request_body(bundle))
        finally:await client.aclose()
    asyncio.run(scenario(httpx.Response(201,content=b'not json'),configuration(bundle),'MALFORMED'))
    asyncio.run(scenario(httpx.Response(307,headers={'location':'https://private.invalid'}),configuration(bundle),'HTTP_ERROR'))
    asyncio.run(scenario(httpx.Response(201,content=b'x'*2048),configuration(bundle,agent_managed_max_response_bytes=1024),'RESPONSE_LIMIT'))


def test_request_budget_reserves_cleanup_attempts(bundle):
    provider=Provider(bundle);provider.status='in_progress'
    async def scenario():
        settings=configuration(bundle,agent_managed_max_requests=8)
        client=ManagedAgentsHTTPClient(settings,transport=httpx.MockTransport(provider),authorized=True)
        journal=[]
        try:
            with pytest.raises(ManagedExecutionError,match='REQUEST_LIMIT'):
                await ManagedCodexAdapter(settings,client).run(bundle,authorized=True,journal=journal.append)
            assert any(x.get('cleanup_state')=='deleted' for x in journal)
            assert journal[-1]['http_request_count']==6
        finally:await client.aclose()
    asyncio.run(scenario())
    assert len(provider.calls)==6 and provider.calls[-2].method=='POST' and provider.calls[-1].method=='DELETE'


@pytest.mark.parametrize('kind',['duplicate','subagent','foreign','unknown_status'])
def test_turn_contract_and_one_turn_limit(bundle,kind):
    provider=Provider(bundle)
    async def handler(req):
        if req.url.path.endswith('/turns'):
            values={'duplicate':[turn(),turn(id='turn_second')],
                    'subagent':[turn(subagent_id='subagent_other')],
                    'foreign':[turn(session_id='sess_other')],
                    'unknown_status':[turn(status='idle')]}
            return httpx.Response(200,json=page(values[kind]))
        return await provider(req)
    with pytest.raises(ManagedExecutionError):asyncio.run(exercise(bundle,handler))
    assert not any(r.url.path.endswith('/items') for r in provider.calls)
    assert provider.calls[-1].method=='DELETE'


def test_item_pagination_filters_commentary_and_reasoning(bundle):
    provider=Provider(bundle)
    async def handler(req):
        if req.url.path.endswith('/items'):
            if 'after' not in req.url.params:
                return httpx.Response(200,json=page([
                    message('not a result',id='msg_commentary',phase='commentary'),
                    {'type':'reasoning','id':'reasoning_one','turn_id':TID,'summary':[{'type':'summary_text','text':'private reasoning canary'}]}],
                    has_more=True,last_id='reasoning_one'))
            assert req.url.params['after']=='reasoning_one'
            return httpx.Response(200,json=page([message(json.dumps(deterministic_analysis(bundle)))]))
        return await provider(req)
    result,_,_=asyncio.run(exercise(bundle,handler))
    assert 'private reasoning canary' not in str(result) and 'not a result' not in str(result)


@pytest.mark.parametrize('bad',['foreign_turn','tool','incomplete','duplicate_final','bad_content','missing_final','large_output'])
def test_result_rejection_and_cleanup(bundle,bad):
    provider=Provider(bundle)
    values={'foreign_turn':[message('{}',turn_id='turn_other')],
            'tool':[{'type':'command_execution','turn_id':TID,'command':'never executed'}],
            'incomplete':[message('{}',status='incomplete')],
            'duplicate_final':[message('{}'),message('{}',id='msg_second')],
            'bad_content':[message('{}',content=[{'type':'input_image'}])],
            'missing_final':[message('{}',phase='commentary')],
            'large_output':[message('界'*45000)]}
    provider.items=values[bad]
    with pytest.raises(ManagedExecutionError):asyncio.run(exercise(bundle,provider))
    assert provider.calls[-2].url.path.endswith('/events') and provider.calls[-1].method=='DELETE'


@pytest.mark.parametrize('kind',['cycle','page_limit'])
def test_pagination_cannot_loop_forever(bundle,kind):
    provider=Provider(bundle);count=0
    async def handler(req):
        nonlocal count
        if req.url.path.endswith('/items'):
            count+=1
            return httpx.Response(200,json=page([],has_more=True,last_id='same' if kind=='cycle' else f'page_{count}'))
        return await provider(req)
    with pytest.raises(ManagedExecutionError):asyncio.run(exercise(bundle,handler,agent_managed_max_pages=2))
    assert count==2 and provider.calls[-1].method=='DELETE'


def test_timeout_during_polling_uses_cleanup_budget(bundle):
    provider=Provider(bundle);reads=0
    async def handler(req):
        nonlocal reads
        if req.method=='GET':reads+=1;await asyncio.sleep(1)
        return await provider(req)
    with pytest.raises(ManagedExecutionError,match='PROVIDER_TIMEOUT'):
        asyncio.run(exercise(bundle,handler,agent_managed_request_timeout_seconds=.01))
    assert reads==2 and provider.calls[-2].url.path.endswith('/events') and provider.calls[-1].method=='DELETE'


def test_cancel_acceptance_is_not_completion_and_failed_cancel_does_not_skip_delete(bundle):
    provider=Provider(bundle);provider.status='failed';cancels=0
    async def handler(req):
        nonlocal cancels
        if req.method=='POST' and req.url.path.endswith('/events'):
            cancels+=1;return httpx.Response(503,json={'error':{'message':'private-body'}})
        return await provider(req)
    async def scenario():
        settings=configuration(bundle);client=ManagedAgentsHTTPClient(settings,transport=httpx.MockTransport(handler),authorized=True)
        journal=[]
        try:
            with pytest.raises(ManagedExecutionError):await ManagedCodexAdapter(settings,client).run(bundle,authorized=True,journal=journal.append)
            assert any(x.get('remote_cancel_acknowledged') is False for x in journal)
            assert any(x.get('cleanup_state')=='deleted' for x in journal)
        finally:await client.aclose()
    asyncio.run(scenario())
    assert cancels==1 and provider.calls[-1].method=='DELETE'


@pytest.mark.parametrize('body',[{'id':SID,'object':'agent.session.deleted','deleted':False},
                               {'id':'sess_other','object':'agent.session.deleted','deleted':True}])
def test_malformed_cleanup_does_not_clear_pending_state(bundle,body):
    provider=Provider(bundle)
    async def handler(req):
        if req.method=='DELETE':return httpx.Response(200,json=body)
        return await provider(req)
    with pytest.raises(ManagedExecutionError,match='CLEANUP_PENDING'):asyncio.run(exercise(bundle,handler))


def test_usage_is_not_double_counted_or_invented(bundle):
    provider=Provider(bundle)
    async def handler(req):
        if req.url.path.endswith(SID) and req.method=='GET':
            return httpx.Response(200,json=session(usage={'input_tokens':1000,'output_tokens':1000,'total_tokens':2000}))
        return await provider(req)
    result,_,_=asyncio.run(exercise(bundle,handler))
    assert result['metadata']['usage']==USAGE
    async def unknown(req):
        if req.url.path.endswith('/turns'):return httpx.Response(200,json=page([turn(usage=None)]))
        return await provider(req)
    result,_,_=asyncio.run(exercise(bundle,unknown))
    assert result['metadata']['usage'] is None


def test_http_client_concurrency_and_identifier_guards(bundle):
    async def scenario():
        provider=Provider(bundle)
        client=ManagedAgentsHTTPClient(configuration(bundle),transport=httpx.MockTransport(provider),authorized=True)
        try:
            await client.create(request_body(bundle))
            with pytest.raises(ProviderError,match='CONCURRENCY'):await client.create(request_body(bundle))
            with pytest.raises(ProviderError,match='IDENTIFIER'):await client.delete('../private')
            with pytest.raises(ProviderError,match='INVALID_CANCEL'):await client.events(SID,{'events':[{'type':'agent.session.input.message'}]})
            await client.delete(SID)
        finally:await client.aclose()
        assert len(provider.calls)==2
    asyncio.run(scenario())


from test_investigations import investigation_api, start, wait
from test_managed_execution import managed_worker_fixture


def test_mock_http_report_usage_and_cleanup_persist_in_sqlite(investigation_api,bundle):
    client,_,worker,*_=investigation_api
    _,adapter=managed_worker_fixture(investigation_api,bundle)
    provider=Provider(bundle)
    adapter.settings=adapter.settings.model_copy(update={'agent_managed_http_enabled':True})
    adapter.client=ManagedAgentsHTTPClient(adapter.settings,transport=httpx.MockTransport(provider),authorized=True)
    row=wait(client,start(investigation_api))
    assert row['status']=='COMPLETED',row
    metadata=row['execution_metadata']
    assert metadata['backend']=='managed-codex' and metadata['mode']=='test-double'
    assert metadata['usage']==USAGE and metadata['usage_source']=='turn'
    assert metadata['cleanup_state']=='deleted' and metadata['http_request_count']==5
    assert metadata['transport']=='agents-beta-http-mock'
    assert row['report']['execution_mode']=='test-double'


def test_mock_http_failure_persists_safe_code_and_cleanup(investigation_api,bundle):
    client,_,worker,*_=investigation_api
    _,adapter=managed_worker_fixture(investigation_api,bundle)
    provider=Provider(bundle)
    async def handler(req):
        if req.method=='GET':return httpx.Response(429,json={'error':{'code':'rate_limit_exceeded','message':'private-error-canary'}})
        return await provider(req)
    adapter.settings=adapter.settings.model_copy(update={'agent_managed_http_enabled':True})
    adapter.client=ManagedAgentsHTTPClient(adapter.settings,transport=httpx.MockTransport(handler),authorized=True)
    row=wait(client,start(investigation_api))
    assert row['status']=='FAILED' and row['report'] is None
    assert row['execution_metadata']['remote_error_code']=='PROVIDER_RATE_LIMIT'
    assert row['execution_metadata']['cleanup_state']=='deleted'
    assert 'private-error-canary' not in str(row)


def test_streamed_response_limit_closes_body(bundle):
    class Body(httpx.AsyncByteStream):
        closed=False
        async def __aiter__(self):
            for _ in range(10):yield b'x'*512
        async def aclose(self):self.closed=True
    body=Body()
    async def scenario():
        client=ManagedAgentsHTTPClient(configuration(bundle,agent_managed_max_response_bytes=1024),
            transport=httpx.MockTransport(lambda r:httpx.Response(201,stream=body)),authorized=True)
        try:
            with pytest.raises(ProviderError,match='RESPONSE_LIMIT'):await client.create(request_body(bundle))
        finally:await client.aclose()
    asyncio.run(scenario())
    assert body.closed
