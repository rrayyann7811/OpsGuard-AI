import hashlib
import hmac
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Literal, Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, UUID4, field_validator
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.models import Incident, IncidentEvent, now

router = APIRouter(prefix="/api", tags=["Incidents"])
Service = Literal["user-service", "order-service", "payment-service"]
Status = Literal["OPEN", "INVESTIGATING", "RESOLVED"]
Severity = Literal["critical", "high", "medium", "low"]


class EventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID4
    service_name: Service
    timestamp: AwareDatetime
    severity: Literal["warning", "error"]
    error_type: str = Field(min_length=1, max_length=128)
    error_message: str = Field(min_length=1, max_length=4096)
    stack_trace: str | None = Field(max_length=16384)
    http_status: int = Field(ge=400, le=599, strict=True)
    request_id: UUID4
    endpoint: str = Field(min_length=1, max_length=512, pattern=r"^/")
    duration_ms: float = Field(strict=True, ge=0, le=86400000, allow_inf_nan=False)

    @field_validator("error_type", "error_message")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("Nonempty text required")
        return value


def redact(value):
    value = re.sub(r"(?i)bearer\s+[^\s,;]+", "Bearer [REDACTED]", value)
    value = re.sub(r"""(?ix)(["']?(?:password|passwd|token|secret|authorization|api[_-]?key)["']?\s*[:=]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s,;]+)""", r"\1[REDACTED]", value)
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", value)
    value = re.sub(r"(https?://)[^/@\s]+:[^/@\s]+@", r"\1[REDACTED]@", value)
    return value


def signature(payload):
    message = re.sub(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", "<uuid>", payload["error_message"].casefold())
    message = " ".join(message.split())
    frames = (payload["stack_trace"] or "").splitlines()[1:]
    frame = next((line.strip() for line in frames if "node:internal" not in line and "node_modules" not in line), "")
    frame = re.sub(r":\d+(?::\d+)?", "", frame)
    frame = re.sub(r"(?:file://)?/(?:[^/()\s]+/)+", "", frame)
    fields = [payload["service_name"], payload["error_type"].casefold(), message, payload["endpoint"], str(payload["http_status"]), frame]
    return hashlib.sha256(json.dumps(fields, separators=(",", ":")).encode()).hexdigest()


def authenticate(authorization, token):
    if not token:
        raise HTTPException(503, "Authentication is not configured")
    if not authorization or not hmac.compare_digest(authorization.encode("utf-8"), ("Bearer " + token).encode("utf-8")):
        raise HTTPException(401, "Invalid credentials", headers={"WWW-Authenticate": "Bearer"})


def webhook_auth(authorization: Annotated[str | None, Header()] = None):
    authenticate(authorization, get_settings().incident_webhook_token)


def management_auth(request: Request, authorization: Annotated[str | None, Header()] = None):
    settings = get_settings()
    if settings.environment != "development" or not settings.enable_incident_management or request.client.host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, "Local incident management is disabled")
    authenticate(authorization, settings.incident_management_token)


def stamp(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def incident_json(row):
    fields = ("id", "service_name", "title", "severity", "status", "error_signature", "error_type", "error_message", "stack_trace", "endpoint", "http_status", "occurrence_count")
    result = {key: getattr(row, key) for key in fields}
    result.update({key: stamp(getattr(row, key)) for key in ("first_seen", "last_seen", "created_at", "updated_at")})
    return result


def find(db, incident_id):
    row = db.get(Incident, str(incident_id))
    if row is None:
        raise HTTPException(404, "Incident not found")
    return row


@router.post("/incidents/events", dependencies=[Depends(webhook_auth)])
def ingest(event: EventInput, db: Session = Depends(get_db)):
    # SQLite write serialization also covers competing first deliveries.
    if db.bind.dialect.name == "sqlite":
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    prior = db.scalar(select(IncidentEvent).where(IncidentEvent.event_id == str(event.event_id)))
    if prior:
        result = {"duplicate": True, "incident": incident_json(find(db, prior.incident_id))}
        db.rollback()
        return result
    evidence = event.model_dump(mode="json")
    for key in ("error_message", "error_type", "stack_trace", "endpoint"):
        if evidence[key] is not None:
            evidence[key] = redact(evidence[key])
    evidence["error_type"] = evidence["error_type"].strip()
    # Queries and fragments are never part of the route evidence.
    evidence["endpoint"] = evidence["endpoint"].split("?", 1)[0].split("#", 1)[0]
    sig = signature(evidence)
    received = now()
    cutoff = received - timedelta(seconds=max(1, get_settings().dedup_window_seconds))
    row = db.scalar(select(Incident).where(Incident.error_signature == sig, Incident.status != "RESOLVED", Incident.last_received_at >= cutoff).order_by(Incident.updated_at.desc()).limit(1))
    source_time = event.timestamp.astimezone(timezone.utc).replace(tzinfo=None)
    if row:
        row.occurrence_count += 1
        row.first_seen = min(row.first_seen, source_time)
        row.last_seen = max(row.last_seen, source_time)
        row.updated_at = received
        row.last_received_at = received
    else:
        row = Incident(service_name=event.service_name, title=f"{evidence['error_type']}: {event.service_name}",
            severity="critical" if event.http_status in (503, 504) else "high" if event.severity == "error" else "medium",
            status="OPEN", error_signature=sig, error_type=evidence["error_type"], error_message=evidence["error_message"],
            stack_trace=evidence["stack_trace"], endpoint=evidence["endpoint"], http_status=event.http_status,
            first_seen=source_time, last_seen=source_time, occurrence_count=1, created_at=received, updated_at=received, last_received_at=received)
        db.add(row)
        db.flush()
    db.add(IncidentEvent(event_id=str(event.event_id), incident_id=row.id, timestamp=source_time,
        request_id=str(event.request_id), error_type=evidence["error_type"], message=evidence["error_message"],
        http_status=event.http_status, duration_ms=event.duration_ms, evidence=evidence))
    db.commit()
    return {"duplicate": False, "incident": incident_json(row)}


@router.get("/incidents/summary")
def summary(db: Session = Depends(get_db)):
    counts = {s: db.scalar(select(func.count()).select_from(Incident).where(Incident.status == s)) for s in ("OPEN", "INVESTIGATING", "RESOLVED")}
    critical = db.scalar(select(func.count()).select_from(Incident).where(Incident.severity == "critical", Incident.status != "RESOLVED"))
    severity = {s: db.scalar(select(func.count()).select_from(Incident).where(Incident.severity == s)) for s in ("critical", "high", "medium", "low")}
    history = db.execute(select(func.date(IncidentEvent.timestamp), func.count()).group_by(func.date(IncidentEvent.timestamp)).order_by(func.date(IncidentEvent.timestamp).desc()).limit(30)).all()
    return {"active": counts["OPEN"] + counts["INVESTIGATING"], "critical": critical, "resolved": counts["RESOLVED"], "total": sum(counts.values()), "by_severity": severity, "history": [{"date": d, "events": c} for d, c in reversed(history)]}


@router.get("/incidents")
def list_incidents(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    severity: Severity | None = None, status: Status | None = None, service: Service | None = None,
    search: str = Query("", max_length=200), db: Session = Depends(get_db)):
    filters = []
    if severity: filters.append(Incident.severity == severity)
    if status: filters.append(Incident.status == status)
    if service: filters.append(Incident.service_name == service)
    if search.strip():
        value = search.strip()
        filters.append(or_(*(column.contains(value, autoescape=True) for column in (Incident.id, Incident.title, Incident.service_name, Incident.error_message))))
    total = db.scalar(select(func.count()).select_from(Incident).where(*filters))
    rows = db.scalars(select(Incident).where(*filters).order_by(Incident.last_seen.desc(), Incident.id.desc()).offset((page-1)*page_size).limit(page_size))
    return {"items": [incident_json(row) for row in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/incidents/{incident_id}")
def detail(incident_id: UUID, db: Session = Depends(get_db)):
    return {"incident": incident_json(find(db, incident_id))}


@router.get("/incidents/{incident_id}/events")
def event_history(incident_id: UUID, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    find(db, incident_id)
    query = select(IncidentEvent).where(IncidentEvent.incident_id == str(incident_id))
    total = db.scalar(select(func.count()).select_from(IncidentEvent).where(IncidentEvent.incident_id == str(incident_id)))
    rows = db.scalars(query.order_by(IncidentEvent.timestamp.desc(), IncidentEvent.id.desc()).offset((page-1)*page_size).limit(page_size))
    return {"items": [{**row.evidence, "id": row.id, "incident_id": row.incident_id} for row in rows], "total": total, "page": page, "page_size": page_size}


class StatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Status


@router.patch("/incidents/{incident_id}/status", dependencies=[Depends(management_auth)])
def change_status(incident_id: UUID, body: StatusInput, db: Session = Depends(get_db)):
    row = find(db, incident_id)
    allowed = {"OPEN": {"INVESTIGATING"}, "INVESTIGATING": {"RESOLVED", "OPEN"}, "RESOLVED": {"OPEN"}}
    if body.status != row.status and body.status not in allowed[row.status]:
        raise HTTPException(409, "Invalid incident status transition")
    row.status = body.status
    row.updated_at = now()
    # last_received_at remains unchanged on status edits.
    db.commit()
    return {"incident": incident_json(row)}


@router.get("/services")
def services(request: Request, db: Session = Depends(get_db)):
    counts = db.execute(select(Incident.service_name, Incident.status, func.count()).group_by(Incident.service_name, Incident.status)).all()
    totals = {}
    for service, status, count in counts:
        item = totals.setdefault(service, {'total':0, 'active':0, 'resolved':0})
        item['total'] += count
        item['resolved' if status == 'RESOLVED' else 'active'] += count
    return {"items": [{**state, 'incident_summary':totals.get(state['service_name'], {'total':0,'active':0,'resolved':0})}
                       for state in request.app.state.monitor.states.values()]}
