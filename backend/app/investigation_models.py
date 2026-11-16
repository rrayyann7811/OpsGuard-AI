from datetime import datetime
from uuid import uuid4
from sqlalchemy import String, Text, DateTime, Float, JSON, ForeignKey, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models import now

ACTIVE = ('QUEUED','COLLECTING_EVIDENCE','RETRIEVING_CONTEXT','INSPECTING_CODE','ANALYZING_GIT','GENERATING_REPORT')
TERMINAL = ('COMPLETED','FAILED','CANCELLED')


class Investigation(Base):
    __tablename__ = 'investigations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda:str(uuid4()))
    incident_id: Mapped[str] = mapped_column(ForeignKey('incidents.id'), index=True)
    service_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    duration_ms: Mapped[float | None] = mapped_column(Float)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    report: Mapped[dict | None] = mapped_column(JSON)
    execution_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (CheckConstraint("status IN ('QUEUED','COLLECTING_EVIDENCE','RETRIEVING_CONTEXT','INSPECTING_CODE','ANALYZING_GIT','GENERATING_REPORT','COMPLETED','FAILED','CANCELLED')"),)


Index('uq_active_investigation_per_incident', Investigation.incident_id, unique=True,
      sqlite_where=Investigation.status.in_(ACTIVE))


class InvestigationEvent(Base):
    __tablename__ = 'investigation_events'
    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey('investigations.id'), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=now)
    status: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text)
