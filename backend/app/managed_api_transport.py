"""Agents beta HTTP transport exercised exclusively through httpx.MockTransport.

No environment credential lookup, socket transport selection, provider probing or
live enablement exists in Phase 5.9. A later live credential/policy gate is required.
"""
import asyncio
import base64
import json
import logging
import math
import httpx
from pydantic import TypeAdapter, ValidationError
from app.agent_reports import AgentAnalysis
from app.managed_codex_adapter import ManagedExecutionError
from app.managed_api_contract import (
    Identifier, CreateSession, CancelRequest, Session, Turn, Page, Message, Deleted,
)

logger = logging.getLogger(__name__)
identifier = TypeAdapter(Identifier)


class ProviderError(ManagedExecutionError):
    def __init__(self, code, status=None):
        self.status = status
        super().__init__(code)


class DeniedTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request):
        raise ProviderError('LIVE_TRANSPORT_NOT_AUTHORIZED')


class ManagedAgentsHTTPClient:
    """Replaceable HTTP implementation of ManagedSessionClient; one active session.

    `authorized` permits mock execution only, never actual provider traffic.
    Unknown creation outcomes block reuse; creates and cancellation POSTs never retry.
    """
    def __init__(self, settings, *, transport=None, authorized=False):
        self.settings = settings
        self.is_test_double = isinstance(transport, httpx.MockTransport)
        self.authorized = authorized is True
        self._http = httpx.AsyncClient(
            base_url='https://api.openai.com/v1/', transport=transport or DeniedTransport(),
            trust_env=False, follow_redirects=False,
            timeout=httpx.Timeout(settings.agent_managed_request_timeout_seconds),
            headers={'OpenAI-Beta': 'agents=v1', 'Content-Type': 'application/json',
                     # Not a credential. Only mock handlers may receive this header.
                     'Authorization': 'Bearer mock-only-not-a-credential'},
        )
        self._active = None
        self._creating = False
        self._unknown_creation = False
        self._counts = {None: 0}
        self._turns = {}
        self._terminal = {}

    @property
    def configured(self):
        return bool(self.is_test_double and self.authorized and self.settings.agent_managed_http_enabled)

    def _fail(self, code, status=None):
        # Never log request/response bodies, IDs, auth headers, URLs, or provider messages.
        logger.warning('managed_http code=%s status=%s', code, status)
        raise ProviderError(code, status) from None

    def _enabled(self):
        if not self.configured:
            self._fail('LIVE_TRANSPORT_NOT_AUTHORIZED')

    def _id(self, value):
        try:
            return identifier.validate_python(value)
        except ValidationError:
            self._fail('INVALID_REMOTE_IDENTIFIER')

    def _parse(self, model, value):
        try:
            return model.model_validate(value)
        except (ValidationError, TypeError, ValueError):
            self._fail('MALFORMED_PROVIDER_RESPONSE')

    def _charge(self, session_id, cleanup):
        count = self._counts.get(session_id, 0)
        # Reserve four attempts for cancel + bounded deletion retries/reconciliation.
        ceiling = self.settings.agent_managed_max_requests - (0 if cleanup else 4)
        if count >= ceiling:
            self._fail('MANAGED_REQUEST_LIMIT')
        self._counts[session_id] = count + 1

    async def _request(self, method, path, *, session_id=None, body=None, params=None, cleanup=False):
        self._enabled()
        retries = self.settings.agent_managed_http_retries if method in ('GET','DELETE') else 0
        for attempt in range(retries + 1):
            self._charge(session_id, cleanup)
            status = None
            retry_after = None
            try:
                async with asyncio.timeout(self.settings.agent_managed_request_timeout_seconds):
                    async with self._http.stream(method, path, json=body, params=params) as response:
                        status = response.status_code
                        retry_after = response.headers.get('retry-after')
                        data = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(data) + len(chunk) > self.settings.agent_managed_max_response_bytes:
                                self._fail('MANAGED_RESPONSE_LIMIT')
                            data.extend(chunk)
                retryable = status in (429,500,502,503,504) or (method == 'DELETE' and status == 409)
                if retryable and attempt < retries:
                    delay = self.settings.agent_managed_retry_delay_seconds
                    if retry_after is not None:
                        try:
                            requested = float(retry_after)
                        except ValueError:
                            self._fail('UNSUPPORTED_RETRY_AFTER', status)
                        if not math.isfinite(requested) or not 0 <= requested <= .2:
                            self._fail('RETRY_AFTER_EXCEEDS_LIMIT', status)
                        delay = max(delay, requested)
                    await asyncio.sleep(delay)
                    continue
                if method == 'DELETE' and status == 404:
                    return None  # Already absent from the public API; not physical-erasure proof.
                expected = {'GET':200, 'POST':201 if path == 'agents/sessions' else 202, 'DELETE':200}[method]
                if status != expected:
                    code = {400:'PROVIDER_INVALID_REQUEST',401:'PROVIDER_AUTHENTICATION',403:'PROVIDER_PERMISSION',
                            404:'PROVIDER_NOT_FOUND',409:'PROVIDER_CONFLICT',429:'PROVIDER_RATE_LIMIT'}.get(status,
                            'PROVIDER_UNAVAILABLE' if status >= 500 else 'PROVIDER_HTTP_ERROR')
                    self._fail(code, status)
                if expected == 202:
                    return None  # Documented empty acknowledgment, not task completion.
                try:
                    return json.loads(data, parse_constant=lambda x: (_ for _ in ()).throw(ValueError()))
                except (ValueError, UnicodeError, RecursionError):
                    self._fail('MALFORMED_PROVIDER_RESPONSE')
            except (httpx.TimeoutException, TimeoutError):
                if attempt < retries:
                    await asyncio.sleep(self.settings.agent_managed_retry_delay_seconds)
                    continue
                self._fail('PROVIDER_TIMEOUT')
            except httpx.TransportError:
                if attempt < retries:
                    await asyncio.sleep(self.settings.agent_managed_retry_delay_seconds)
                    continue
                self._fail('PROVIDER_UNAVAILABLE')

    async def create(self, request):
        self._enabled()
        if self._active is not None or self._creating or self._unknown_creation:
            self._fail('MANAGED_CONCURRENCY_OR_UNKNOWN_CREATE')
        try:
            parsed = CreateSession.model_validate(request)
            if parsed.agent.text.format.schema_ != AgentAnalysis.model_json_schema():
                raise ValueError('Unexpected schema')
            data = base64.b64decode(parsed.environment.files[0].data, validate=True)
            if len(data) > self.settings.agent_managed_max_evidence_bytes:
                raise ValueError('Evidence size')
        except (ValueError, ValidationError, TypeError):
            self._fail('INVALID_MANAGED_REQUEST')
        self._counts[None] = 0
        self._creating = True
        try:
            wire = await self._request('POST','agents/sessions',body=parsed.model_dump(by_alias=True))
            session = self._parse(Session, wire)
            self._active = session.id
            self._counts[session.id] = self._counts.pop(None)
            return {'id':session.id}
        except BaseException:
            self._unknown_creation = True
            raise
        finally:
            self._creating = False

    async def _pages(self, path, session_id):
        after, seen, items = None, set(), []
        for _ in range(self.settings.agent_managed_max_pages):
            params = {'order':'asc','limit':100}
            if after: params['after'] = after
            page = self._parse(Page, await self._request('GET',path,session_id=session_id,params=params))
            items.extend(page.data)
            if not page.has_more: return items
            if page.last_id is None or page.last_id in seen:
                self._fail('INVALID_PROVIDER_PAGINATION')
            after = page.last_id
            seen.add(after)
        self._fail('MANAGED_PAGE_LIMIT')

    async def observe(self, session_id):
        session_id = self._id(session_id)
        session = self._parse(Session, await self._request('GET',f'agents/sessions/{session_id}',session_id=session_id))
        if session.id != session_id: self._fail('PROVIDER_SESSION_MISMATCH')
        if session.status == 'failed':
            self._terminal[session_id] = 'failed'
            return {'terminal_event':'agent.session.turn.failed',
                    'usage': session.usage.model_dump(exclude_none=True) if session.usage else None, 'usage_source':'session'}
        if session.status == 'requires_action' or session.required_actions:
            return {'requires_action':True}
        turns = [self._parse(Turn,x) for x in await self._pages(f'agents/sessions/{session_id}/turns',session_id)]
        if any(t.session_id != session_id or t.subagent_id is not None for t in turns):
            self._fail('UNEXPECTED_PROVIDER_TURN')
        if len(turns) > 1: self._fail('MANAGED_SESSION_TURN_LIMIT')
        if not turns: return {}
        turn = turns[0]
        old = self._turns.get(session_id)
        if old is not None and old.id != turn.id: self._fail('PROVIDER_TURN_CHANGED')
        self._turns[session_id] = turn
        usage = turn.usage.model_dump(exclude_none=True) if turn.usage else None
        if turn.status == 'waiting': return {'requires_action':True, 'usage':usage, 'usage_source':'turn'}
        if turn.status in ('completed','failed','cancelled'):
            self._terminal[session_id] = turn.status
            # These event names are the existing port's normalized observation, not SSE.
            return {'terminal_event':f'agent.session.turn.{turn.status}',
                    'usage':usage, 'usage_source':'turn'}
        return {'usage':usage, 'usage_source':'turn'}

    async def result(self, session_id, max_bytes):
        session_id = self._id(session_id)
        turn = self._turns.get(session_id)
        if turn is None or turn.status != 'completed' or self._terminal.get(session_id) != 'completed':
            self._fail('REMOTE_RESULT_NOT_COMPLETED')
        items = await self._pages(f'agents/sessions/{session_id}/items',session_id)
        outputs = []
        for raw in items:
            if raw.get('turn_id') != turn.id:
                self._fail('PROVIDER_ITEM_TURN_MISMATCH')
            if raw.get('type') == 'reasoning': continue  # Never expose/save private reasoning.
            if raw.get('type') != 'message': self._fail('UNEXPECTED_PROVIDER_TOOL_ACTIVITY')
            message = self._parse(Message,raw)
            if message.role != 'assistant' or message.phase != 'final_answer': continue
            if message.status != 'completed': self._fail('INCOMPLETE_PROVIDER_MESSAGE')
            if not message.content or any(c.type != 'output_text' or c.text is None for c in message.content):
                self._fail('UNSUPPORTED_PROVIDER_CONTENT')
            outputs.append(''.join(c.text for c in message.content))
        if len(outputs) != 1: self._fail('AMBIGUOUS_PROVIDER_RESULT')
        if len(outputs[0].encode()) > min(max_bytes,self.settings.agent_managed_max_output_bytes):
            self._fail('REMOTE_OUTPUT_LIMIT')
        # A fresh turn snapshot is the usage source; never add session and turn totals.
        usage = turn.usage.model_dump(exclude_none=True) if turn.usage else None
        return {'output_text':outputs[0], 'usage':usage, 'usage_source':'turn' if usage else None}

    async def events(self, session_id, request):
        session_id = self._id(session_id)
        try:
            parsed = CancelRequest.model_validate(request)
        except ValidationError:
            self._fail('INVALID_CANCEL_REQUEST')
        await self._request('POST',f'agents/sessions/{session_id}/events',session_id=session_id,
                            body=parsed.model_dump(),cleanup=True)

    async def delete(self, session_id):
        session_id = self._id(session_id)
        body = await self._request('DELETE',f'agents/sessions/{session_id}',session_id=session_id,cleanup=True)
        if body is not None:
            deleted = self._parse(Deleted,body)
            if deleted.id != session_id: self._fail('PROVIDER_SESSION_MISMATCH')
        if self._active == session_id: self._active = None
        self._terminal.pop(session_id,None)
        self._turns.pop(session_id,None)

    def diagnostics(self, session_id):
        return {'http_request_count':self._counts.get(session_id,0),'transport':'agents-beta-http-mock',
                'live_transport_authorized':False}

    async def aclose(self):
        await self._http.aclose()
