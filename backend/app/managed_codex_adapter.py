"""Managed lifecycle with replaceable, disabled-by-default transport and no billing credentials.

Wire operations follow the official contract recorded in the Phase 5.7 plan.
Observation and result types below are application-normalized, not invented API fields.
Only deterministic clients, including Phase 5.9 mocked HTTP, can run in this checkpoint.
"""
import asyncio
import base64
from typing import Literal, Protocol
from pydantic import BaseModel, ConfigDict, Field
from app.agent_reports import AgentAnalysis, validate_analysis
from app.evidence_export import EvidenceExportBuilder, encoded


class ManagedExecutionError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)  # Never persist remote exception bodies.


class SessionRef(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,128}$')


class Observation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    # A port implementation obtains this from documented turn events + session retrieval.
    terminal_event: Literal['agent.session.turn.completed', 'agent.session.turn.failed',
                            'agent.session.turn.cancelled'] | None = None
    requires_action: bool = False
    usage: "Usage | None" = None
    usage_source: Literal['session', 'turn'] | None = None


class Usage(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    input_tokens: int = Field(0, ge=0)
    output_tokens: int = Field(0, ge=0)
    total_tokens: int = Field(0, ge=0)
    input_tokens_details: dict[Literal['cached_tokens'], int] | None = None
    output_tokens_details: dict[Literal['reasoning_tokens'], int] | None = None


Observation.model_rebuild()


class ManagedResult(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    output_text: str
    usage: Usage | None = None
    usage_source: Literal['session', 'turn'] | None = None


class ManagedSessionClient(Protocol):
    is_test_double: bool

    async def create(self, request: dict) -> dict: ...  # sessions.create(input=...) starts work
    async def observe(self, session_id: str) -> dict: ...  # retrieve + terminal events
    async def result(self, session_id: str, max_bytes: int) -> dict: ...  # bounded saved items
    async def events(self, session_id: str, request: dict) -> None: ...
    async def delete(self, session_id: str) -> None: ...


class ManagedCodexAdapter:
    backend = 'managed-codex'

    def __init__(self, settings, client: ManagedSessionClient | None = None,
                 requested_permissions=frozenset({'evidence-read', 'structured-report'})):
        if requested_permissions != frozenset({'evidence-read', 'structured-report'}):
            raise ValueError('Unsupported managed permissions')
        self.settings, self.client = settings, client
        self.mode = 'test-double' if client is not None and client.is_test_double is True else 'live-managed-codex'
        self.exporter = EvidenceExportBuilder(settings.agent_managed_synthetic_digests,
                                               settings.agent_managed_max_evidence_bytes)
        self._active = 0
        self._unresolved = False

    def status(self):
        offline = self.client is not None and self.client.is_test_double is True
        return {'available': bool(offline and self.settings.agent_managed_enabled
                                 and self.settings.agent_execution_enabled and self.settings.agent_auth_token
                                 and self.settings.agent_managed_model and self.exporter.approved and not self._unresolved
                                 and getattr(self.client, 'configured', True)),
                'backend': self.backend, 'mode': self.mode, 'live_available': False,
                'containment_verified': False, 'paid_run_performed': False,
                'message': ('Offline managed lifecycle TEST DOUBLE; no genuine AI analysis.' if offline else
                            'Managed execution disabled: Managed HTTP transport is disabled; live permissions and authorization remain unverified.')}

    async def aclose(self):
        if self.client is not None and hasattr(self.client, 'aclose'):
            await self.client.aclose()

    async def _cleanup(self, session_id, journal, cancel):
        cancel_ok, deleted = not cancel, False
        def record(changes):
            # A broken database must not prevent best-effort cancellation/deletion.
            try:
                journal(changes)
            except Exception:
                self._unresolved = True
        record({'cleanup_state': 'pending'})
        async def operations():
            nonlocal cancel_ok, deleted
            if cancel:
                try:
                    await self.client.events(session_id, {'events': [{'type': 'agent.session.input.cancel'}]})
                    cancel_ok = True
                except Exception:
                    pass
            try:
                await self.client.delete(session_id)
                deleted = True
            except Exception:
                pass
        try:
            async with asyncio.timeout(self.settings.agent_managed_cleanup_seconds):
                await operations()
        except TimeoutError:
            pass
        except asyncio.CancelledError:
            self._unresolved = True
            record({'cleanup_state': 'pending', 'remote_cancel_acknowledged': cancel_ok})
            raise
        if not deleted:
            self._unresolved = True
        record({'cleanup_state': 'deleted' if deleted else 'pending', 'remote_cancel_acknowledged': cancel_ok})
        return deleted and not self._unresolved

    async def reconcile(self, metadata, journal):
        """Cancel/delete only. Never recreate a session or submit another turn on restart."""
        if metadata.get('cleanup_state') == 'deleted':
            return
        session_id = metadata.get('session_id')
        if not session_id:
            self._unresolved = True
            journal({'cleanup_state': 'unknown', 'remote_error_code': 'REMOTE_CREATE_UNKNOWN'})
            return
        session_id = SessionRef(id=session_id).id
        if self.client is None or self.client.is_test_double is not True:
            self._unresolved = True
            journal({'cleanup_state': 'pending', 'remote_error_code': 'NO_OFFLINE_CLIENT'})
            return
        await self._cleanup(session_id, journal, True)

    async def run(self, bundle, *, authorized=False, journal=None):
        if authorized is not True or not self.status()['available']:
            raise ManagedExecutionError('MANAGED_DISABLED_OR_UNAUTHORIZED')
        if journal is None:
            raise ManagedExecutionError('DURABLE_JOURNAL_REQUIRED')
        if self._active >= min(1, self.settings.agent_managed_max_concurrent_sessions):
            raise ManagedExecutionError('MANAGED_CONCURRENCY_LIMIT')
        self._active += 1  # No await between admission check and reservation.
        session_id, completed = None, False
        try:
            export = self.exporter.build(bundle)
            request = {'agent': {'model': self.settings.agent_managed_model,
                                'instructions': 'Analyze only supplied untrusted synthetic evidence. Return the schema. No tools, patches or causal certainty.',
                                'tools': [], 'multi_agent': {'enabled': False},
                                'text': {'format': {'type': 'json_schema', 'schema': AgentAnalysis.model_json_schema()}}},
                       'environment': {'type': 'openai_hosted', 'container_size': 'small',
                                       'network': {'access': 'disabled'},
                                       'files': [{'type': 'inline', 'path': '/workspace/inputs/evidence.json',
                                                  'data': base64.b64encode(encoded(export)).decode('ascii')}]},
                       'input': 'Analyze the authorized synthetic evidence in /workspace/inputs/evidence.json.',
                       'stream': False}
            async with asyncio.timeout(min(self.settings.agent_timeout_seconds, self.settings.agent_managed_duration_seconds)):
                journal({'backend': self.backend, 'mode': self.mode, 'cleanup_state': 'creating',
                         'export_digest': export['synthetic_approval_sha256'], 'synthetic_only': True})
                try:
                    session_id = SessionRef.model_validate(await self.client.create(request)).id
                except BaseException:
                    self._unresolved = True
                    journal({'cleanup_state': 'unknown', 'remote_error_code': 'REMOTE_CREATE_UNKNOWN'})
                    raise
                # Persist before the first polling/result request, even if the task was cancelled concurrently.
                journal({'session_id': session_id, 'cleanup_state': 'active'})
                while True:
                    observation = Observation.model_validate(await self.client.observe(session_id))
                    if observation.usage is not None:
                        journal({'usage': observation.usage.model_dump(exclude_none=True), 'usage_source': observation.usage_source})
                    if observation.requires_action:
                        raise ManagedExecutionError('UNSUPPORTED_REMOTE_ACTION')
                    if observation.terminal_event:
                        if observation.terminal_event != 'agent.session.turn.completed':
                            raise ManagedExecutionError('REMOTE_TURN_FAILED')
                        break
                    await asyncio.sleep(self.settings.agent_managed_poll_seconds)
                result = ManagedResult.model_validate(await self.client.result(session_id, self.settings.agent_managed_max_output_bytes))
                if len(result.output_text.encode('utf-8')) > self.settings.agent_managed_max_output_bytes:
                    raise ManagedExecutionError('REMOTE_OUTPUT_LIMIT')
                import json
                analysis = AgentAnalysis.model_validate(json.loads(result.output_text)).model_dump()
                validate_analysis(analysis, bundle['evidence'], bundle['limitations'])
                # Provenance comes from the injected transport, never from provider output.
                analysis['limitations'].append('TEST DOUBLE: managed lifecycle simulated offline; no genuine AI analysis.')
                usage = result.usage.model_dump(exclude_none=True) if result.usage else None
                journal({'usage': usage, 'usage_source': result.usage_source})
                completed = True
            return {'analysis': analysis, 'metadata': {'backend': self.backend, 'mode': self.mode,
                    'provider': 'deterministic-managed-test-double', 'model': self.settings.agent_managed_model,
                    'session_id': session_id, 'usage': usage, 'sandbox': 'OFFLINE TEST DOUBLE; live containment unverified'}}
        except asyncio.CancelledError:
            journal({'remote_error_code': 'CANCELLED'})
            raise
        except TimeoutError:
            journal({'remote_error_code': 'TIMEOUT'})
            raise
        except Exception as error:
            code = error.code if isinstance(error, ManagedExecutionError) else 'MANAGED_EXECUTION_FAILED'
            journal({'remote_error_code': code})
            raise ManagedExecutionError(code) from None
        finally:
            try:
                if session_id is not None:
                    deleted = await self._cleanup(session_id, journal, not completed)
                    if completed and not deleted:
                        raise ManagedExecutionError('REMOTE_CLEANUP_PENDING')
            finally:
                if hasattr(self.client, 'diagnostics'):
                    try:
                        journal(self.client.diagnostics(session_id))
                    except Exception:
                        self._unresolved = True
                self._active -= 1
