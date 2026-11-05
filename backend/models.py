"""SQLAlchemy models for hardware, diagnostics, tickets, users, and audit history."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, event
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(20), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class HardwareUnit(Base):
    __tablename__ = "hardware_units"

    hardware_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    model_type: Mapped[str] = mapped_column(String(20), index=True)
    district: Mapped[str] = mapped_column(String(100), index=True)
    sector: Mapped[str] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DiagnosticTree(Base):
    __tablename__ = "diagnostic_trees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    appliance_type: Mapped[str] = mapped_column(String(20), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ServiceTicket(Base):
    __tablename__ = "service_tickets"
    __table_args__ = (
        Index("ix_service_tickets_status_priority", "status", "priority"),
        Index("ix_service_tickets_zone", "district", "sector"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_ticket_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    hardware_id: Mapped[str] = mapped_column(ForeignKey("hardware_units.hardware_id"), index=True)
    model_type: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), default="Open", index=True)
    priority: Mapped[str] = mapped_column(String(20), index=True)
    fault_category: Mapped[str] = mapped_column(String(120), index=True)
    fault_code: Mapped[dict] = mapped_column(JSON, nullable=False)
    diagnostic_path: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    requires_technician: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    district: Mapped[str] = mapped_column(String(100), index=True)
    sector: Mapped[str] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int | None] = mapped_column(ForeignKey("service_tickets.id"), nullable=True, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


def _immutable_audit_row(*_args: object, **_kwargs: object) -> None:
    raise ValueError("Audit log rows are immutable.")


# Audit history is append-only so ticket creation and status changes remain verifiable.
event.listen(AuditLog, "before_update", _immutable_audit_row)
event.listen(AuditLog, "before_delete", _immutable_audit_row)
