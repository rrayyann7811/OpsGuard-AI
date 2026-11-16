"""Explicit execution selection; no failure fallback and disabled managed HTTP selection."""
from app.codex_adapter import CodexAdapter
from app.managed_codex_adapter import ManagedCodexAdapter
from app.test_double_adapter import DeterministicAdapter


def create_adapter(settings):
    if settings.agent_execution_backend == 'local-ollama':
        from app.ollama_adapter import OllamaAdapter
        return OllamaAdapter(settings)
    if settings.agent_execution_backend == 'local-codex':
        return CodexAdapter(settings)
    if settings.agent_execution_backend == 'managed-codex':
        if settings.agent_managed_http_enabled:
            from app.managed_api_transport import ManagedAgentsHTTPClient
            return ManagedCodexAdapter(settings, ManagedAgentsHTTPClient(settings))
        return ManagedCodexAdapter(settings)
    if settings.agent_execution_backend == 'test-double':
        return DeterministicAdapter(settings)
    raise ValueError('Unknown execution backend')


def backend_name(adapter):
    return getattr(adapter, 'backend', 'test-double' if adapter.mode == 'test-double' else 'local-codex')
