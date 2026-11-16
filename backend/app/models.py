from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey, JSON, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    service_name: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(256))
    severity: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", index=True)
    error_signature: Mapped[str] = mapped_column(String(64), index=True)
    error_type: Mapped[str] = mapped_column(String(128))
    error_message: Mapped[str] = mapped_column(Text)
    stack_trace: Mapped[str | None] = mapped_column(Text)
    endpoint: Mapped[str] = mapped_column(String(512))
    http_status: Mapped[int] = mapped_column(Integer)
    first_seen: Mapped[datetime] = mapped_column(DateTime)
    last_seen: Mapped[datetime] = mapped_column(DateTime, index=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    last_received_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (
        CheckConstraint("status IN ('OPEN','INVESTIGATING','RESOLVED')"),
        CheckConstraint("occurrence_count >= 1"),
        Index("ix_incident_dedup", "error_signature", "status", "last_received_at"),
    )


class IncidentEvent(Base):
    __tablename__ = "incident_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    request_id: Mapped[str] = mapped_column(String(36), index=True)
    error_type: Mapped[str] = mapped_column(String(128))
    message: Mapped[str] = mapped_column(Text)
    http_status: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[float] = mapped_column(Float)
    evidence: Mapped[dict] = mapped_column("metadata", JSON)
