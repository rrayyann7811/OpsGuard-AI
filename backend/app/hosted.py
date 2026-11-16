"""Option A: stateless, read-only cloud API. No DB, workers, models or outbound I/O.

This entry point deliberately does not import app.main or app.database.
The full local application remains app.main:app.
"""
from ipaddress import ip_address
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class HostedSettings(BaseSettings):
    cors_origins: list[str] = []
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    @field_validator("cors_origins")
    @classmethod
    def exact_https_origins(cls, origins):
        for origin in origins:
            url = urlsplit(origin)
            host = url.hostname or ""
            try:
                private = not ip_address(host).is_global
            except ValueError:
                private = host == "localhost" or host.endswith((".localhost", ".local"))
            if (url.scheme != "https" or not host or private or "*" in origin
                    or url.username or url.password or url.path or url.query or url.fragment):
                raise ValueError("CORS_ORIGINS must contain exact public HTTPS origins without paths or credentials")
        return origins


def create_app(settings: HostedSettings | None = None):
    settings = settings or HostedSettings()
    app = FastAPI(title="OpsGuard AI read-only cloud API", version="0.1.0")

    @app.middleware("http")
    async def read_only(request: Request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            return JSONResponse(status_code=403, content={"detail": "Hosted API is read-only. Ingestion, management, retrieval execution and investigations are disabled."})
        return await call_next(request)

    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_credentials=False, allow_methods=["GET", "HEAD", "OPTIONS"],
                       allow_headers=["Accept", "Content-Type"])

    @app.get("/api/health")
    def health():
        return {"status": "healthy", "service": "OpsGuard AI", "version": "0.1.0",
                "environment": "production", "mode": "hosted-readonly",
                "database": "not_configured", "storage": "stateless",
                "capabilities": {"incident_writes": False, "monitoring": False,
                                 "historical_retrieval": False, "investigations": False}}

    @app.get("/api/incidents/summary")
    def incident_summary():
        return {"active": 0, "critical": 0, "resolved": 0, "total": 0,
                "by_severity": {x: 0 for x in ("critical", "high", "medium", "low")}, "history": []}

    @app.get("/api/incidents")
    def incidents(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                  severity: Literal["critical", "high", "medium", "low"] | None = None,
                  status: Literal["OPEN", "INVESTIGATING", "RESOLVED"] | None = None,
                  service: Literal["user-service", "order-service", "payment-service"] | None = None,
                  search: str = Query("", max_length=200)):
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    @app.get("/api/incidents/{incident_id}")
    @app.get("/api/incidents/{incident_id}/events")
    def missing_incident(incident_id: UUID):
        raise HTTPException(404, "No incident records are stored by this stateless hosted API")

    @app.get("/api/services")
    def services():
        return {"items": [{"service_name": name, "status": "Unknown", "available": None,
                           "last_success": None, "last_attempt": None, "latency_ms": None,
                           "consecutive_failures": 0, "failure_reason": "Microservices are not deployed; monitoring is disabled.",
                           "incident_summary": {"total": 0, "active": 0, "resolved": 0}}
                          for name in ("user-service", "order-service", "payment-service")]}

    @app.get("/api/investigations/configuration")
    def configuration():
        return {"available": False, "mode": "hosted-readonly", "backend": "disabled",
                "read_only": True, "message": "Investigation execution is disabled on this hosted API. No model or worker is deployed."}

    @app.get("/api/investigations/readiness")
    def readiness():
        return {"backend": "disabled", "model_configured": False, "execution_enabled": False,
                "action_token_configured": False, "memory_guard": "not_applicable",
                "live_inference_verified": False, "verification_status": "pending", "can_start": False}

    @app.get("/api/investigations/summary")
    def investigation_summary():
        return {"total": 0, "completed": 0, "running": 0, "failed": 0, "cancelled": 0, "average_duration_ms": None}

    @app.get("/api/investigations")
    def investigations(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), incident_id: UUID | None = None):
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    @app.get("/api/investigations/{job_id}")
    @app.get("/api/investigations/{job_id}/events")
    @app.get("/api/investigations/{job_id}/report")
    def missing_job(job_id: UUID):
        raise HTTPException(404, "No investigations are stored by this stateless hosted API")

    @app.get("/api/knowledge/status")
    def knowledge_status():
        return {"status": "unavailable", "mode": "not_deployed", "collection": None,
                "indexed_incidents": None, "indexed_chunks": None, "source_count": None,
                "last_indexed_at": None, "embedding_model": "Not deployed", "dimension": None,
                "embedding_loaded": False, "message": "Historical retrieval is unavailable: Qdrant and embeddings are not deployed."}

    @app.get("/api/knowledge/incidents")
    @app.get("/api/knowledge/incidents/{document_id}")
    def knowledge_unavailable(document_id: str | None = None):
        raise HTTPException(503, "Historical knowledge is not deployed on this hosted API")

    return app


app = create_app()
