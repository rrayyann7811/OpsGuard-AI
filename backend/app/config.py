from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "OpsGuard AI"
    environment: str = "development"
    database_url: str = "sqlite:///./opsguard.db"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    incident_webhook_token: str = ""
    incident_management_token: str = ""
    enable_incident_management: bool = False
    dedup_window_seconds: int = Field(300, ge=1, le=86400)
    monitor_enabled: bool = True
    monitor_interval_seconds: float = Field(10, ge=.1, le=3600)
    monitor_timeout_seconds: float = Field(1, ge=.05, le=5)
    monitor_degraded_ms: float = Field(500, ge=0, le=60000)
    user_service_url: str = "http://127.0.0.1:3001"
    order_service_url: str = "http://127.0.0.1:3002"
    payment_service_url: str = "http://127.0.0.1:3003"
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_path: str = str(Path(__file__).resolve().parents[2] / "knowledge/.qdrant")
    qdrant_collection: str = Field("opsguard_history_v1", pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    embedding_model: str = Field("sentence-transformers/all-MiniLM-L6-v2", min_length=1, max_length=300)
    embedding_revision: str = Field("c9745ed1d9f207416be6d2e6f8de32d1f16199bf", pattern=r"^[0-9a-f]{40}$")
    embedding_dimension: int = Field(384, ge=1, le=4096)
    embedding_local_only: bool = True

    agent_execution_backend: Literal["local-codex", "local-ollama", "managed-codex", "test-double"] = "local-ollama"
    agent_ollama_url: str = "http://127.0.0.1:11434"
    agent_ollama_model: str = Field("", max_length=128, pattern=r'^[A-Za-z0-9_.:/-]*$')
    agent_ollama_timeout_seconds: float = Field(60, ge=.01, le=180)
    agent_ollama_retries: int = Field(1, ge=0, le=1)
    agent_ollama_max_prompt_bytes: int = Field(24576, ge=1024, le=65536)
    agent_ollama_max_output_bytes: int = Field(16384, ge=1024, le=65536)
    agent_ollama_context_tokens: int = Field(8192, ge=2048, le=8192)
    agent_ollama_output_tokens: int = Field(1536, ge=256, le=2048)
    agent_ollama_max_model_bytes: int = Field(2500000000, ge=1, le=3000000000)
    agent_ollama_min_available_bytes: int = Field(2147483648, ge=1073741824)
    agent_managed_enabled: bool = False
    agent_managed_http_enabled: bool = False
    agent_managed_request_timeout_seconds: float = Field(2, ge=.01, le=30)
    agent_managed_max_requests: int = Field(32, ge=8, le=100)
    agent_managed_http_retries: int = Field(1, ge=0, le=2)
    agent_managed_retry_delay_seconds: float = Field(.01, ge=0, le=.2)
    agent_managed_max_response_bytes: int = Field(262144, ge=1024, le=1048576)
    agent_managed_max_pages: int = Field(4, ge=1, le=8)
    agent_managed_model: str = Field("", max_length=128)
    agent_managed_max_investigations_per_session: int = Field(1, ge=1, le=1)
    agent_managed_max_concurrent_sessions: int = Field(1, ge=1, le=1)
    agent_managed_max_evidence_bytes: int = Field(131072, ge=1024, le=131072)
    agent_managed_max_output_bytes: int = Field(131072, ge=1024, le=131072)
    agent_managed_duration_seconds: float = Field(60, ge=.01, le=180)
    agent_managed_poll_seconds: float = Field(.05, ge=.001, le=5)
    agent_managed_cleanup_seconds: float = Field(2, ge=.01, le=10)
    agent_managed_synthetic_digests: list[str] = []
    agent_execution_enabled: bool = False
    agent_auth_token: str = ""
    agent_codex_api_key: SecretStr = SecretStr("")
    agent_codex_model: str = Field("", max_length=128)
    agent_project_root: str = str(Path(__file__).resolve().parents[2])
    agent_timeout_seconds: int = Field(90, ge=5, le=180)
    agent_queue_limit: int = Field(8, ge=1, le=20)

    @field_validator("agent_ollama_url")
    @classmethod
    def ollama_loopback_only(cls, value):
        # Numeric loopback only: no DNS, rebinding, proxy, credentials or cloud endpoint.
        parsed = urlsplit(value)
        if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', '::1')
                or parsed.username or parsed.password or parsed.path not in ('', '/')
                or parsed.query or parsed.fragment or not parsed.port):
            raise ValueError('Ollama requires an explicit HTTP numeric-loopback origin and port')
        return value.rstrip('/')

    @field_validator("agent_managed_synthetic_digests")
    @classmethod
    def synthetic_digests(cls, values):
        import re
        if len(values) > 100 or any(not re.fullmatch(r"[0-9a-f]{64}", x) for x in values):
            raise ValueError("Synthetic approvals must be exact SHA-256 digests")
        return values

    @field_validator("qdrant_url")
    @classmethod
    def vector_server_url(cls, value):
        if not value:
            return value
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Qdrant URL must be HTTP(S) without embedded credentials or query")
        return value.rstrip("/")

    @field_validator("user_service_url", "order_service_url", "payment_service_url")
    @classmethod
    def service_url(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Service URL must be HTTP(S) without credentials or query")
        return value.rstrip("/")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
