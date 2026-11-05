"""Ticket synchronization, technician dispatch, and status history."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, HardwareUnit, ServiceTicket, User
from ..schemas import (
    TicketPriority,
    TicketResponse,
    TicketStatus,
    TicketStatusUpdate,
    TicketSyncRequest,
    TicketSyncResponse,
    TicketSyncResult,
)
from ..services import log_mock_sms_notification
from .auth import get_current_user, require_role

router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def _immutable_data_matches(ticket: ServiceTicket, item) -> bool:
    return (
        ticket.hardware_id == item.hardware_id
        and ticket.model_type == item.model_type
        and ticket.priority == item.priority
        and ticket.fault_category == item.fault_category
        and ticket.fault_code == item.fault_code.model_dump()
        and ticket.diagnostic_path == [step.model_dump() for step in item.diagnostic_path]
    )


@router.post("/sync", response_model=TicketSyncResponse)
def sync_tickets(payload: TicketSyncRequest, db: DatabaseSession) -> TicketSyncResponse:
    """Idempotently accept offline tickets and notify dispatch for newly created ones."""
    results: list[TicketSyncResult] = []
    synced = 0
    rejected = 0

    # Report results per ticket so one invalid offline record does not block its batch.
    for item in payload.tickets:
        existing = db.scalar(
            select(ServiceTicket).where(ServiceTicket.client_ticket_id == item.client_ticket_id)
        )
        if existing is not None:
            if not _immutable_data_matches(existing, item):
                results.append(
                    TicketSyncResult(
                        client_ticket_id=item.client_ticket_id,
                        result="rejected",
                        message="This ticket ID was already used with different diagnostic data.",
                    )
                )
                rejected += 1
            else:
                results.append(
                    TicketSyncResult(
                        client_ticket_id=item.client_ticket_id,
                        result="already_synced",
                        ticket_id=existing.id,
                    )
                )
                synced += 1
            continue

        unit = db.get(HardwareUnit, item.hardware_id)
        if unit is None or unit.model_type != item.model_type:
            results.append(
                TicketSyncResult(
                    client_ticket_id=item.client_ticket_id,
                    result="rejected",
                    message="The hardware ID is not registered for this model.",
                )
            )
            rejected += 1
            continue

        if item.fault_code.category != item.fault_category:
            results.append(
                TicketSyncResult(
                    client_ticket_id=item.client_ticket_id,
                    result="rejected",
                    message="The fault category does not match the fault-code payload.",
                )
            )
            rejected += 1
            continue

        ticket = ServiceTicket(
            client_ticket_id=item.client_ticket_id,
            hardware_id=unit.hardware_id,
            model_type=unit.model_type,
            status="Open",
            priority=item.priority,
            fault_category=item.fault_category,
            fault_code=item.fault_code.model_dump(),
            diagnostic_path=[step.model_dump() for step in item.diagnostic_path],
            requires_technician=True,
            district=unit.district,
            sector=unit.sector,
        )
        try:
            with db.begin_nested():
                db.add(ticket)
                db.flush()
        except IntegrityError:
            concurrent_ticket = db.scalar(
                select(ServiceTicket).where(ServiceTicket.client_ticket_id == item.client_ticket_id)
            )
            if concurrent_ticket is not None and _immutable_data_matches(concurrent_ticket, item):
                results.append(
                    TicketSyncResult(
                        client_ticket_id=item.client_ticket_id,
                        result="already_synced",
                        ticket_id=concurrent_ticket.id,
                    )
                )
                synced += 1
            else:
                results.append(
                    TicketSyncResult(
                        client_ticket_id=item.client_ticket_id,
                        result="rejected",
                        message="This ticket could not be saved because its ID conflicts with another ticket.",
                    )
                )
                rejected += 1
            continue
        db.add(
            AuditLog(
                ticket_id=ticket.id,
                event_type="TICKET_CREATED",
                # Preserve the exact traversal separately from future technician status events.
                details={
                    "client_ticket_id": item.client_ticket_id,
                    "hardware_id": unit.hardware_id,
                    "model_type": unit.model_type,
                    "fault_code": item.fault_code.model_dump(),
                    "diagnostic_path": [step.model_dump() for step in item.diagnostic_path],
                    "status": "Open",
                },
            )
        )
        log_mock_sms_notification(db, ticket)
        results.append(
            TicketSyncResult(
                client_ticket_id=item.client_ticket_id,
                result="synced",
                ticket_id=ticket.id,
            )
        )
        synced += 1

    db.commit()
    return TicketSyncResponse(results=results, synced=synced, rejected=rejected)


@router.get("", response_model=list[TicketResponse])
def list_tickets(
    db: DatabaseSession,
    user: Annotated[User, Depends(require_role("technician", "admin"))],
    status_filter: Annotated[TicketStatus | None, Query(alias="status")] = None,
    priority: TicketPriority | None = None,
) -> list[ServiceTicket]:
    # A technician sees only their zone; closed tickets leave the active queue by default.
    statement = select(ServiceTicket).where(ServiceTicket.requires_technician.is_(True))
    if status_filter is not None:
        statement = statement.where(ServiceTicket.status == status_filter)
    else:
        statement = statement.where(ServiceTicket.status != "Closed")
    if priority is not None:
        statement = statement.where(ServiceTicket.priority == priority)
    if user.district:
        statement = statement.where(ServiceTicket.district == user.district)
    if user.sector:
        statement = statement.where(ServiceTicket.sector == user.sector)
    return list(db.scalars(statement.order_by(ServiceTicket.created_at.desc())).all())


@router.patch("/{ticket_id}/status", response_model=TicketResponse)
def update_ticket_status(
    ticket_id: int,
    payload: TicketStatusUpdate,
    db: DatabaseSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ServiceTicket:
    if user.role not in {"technician", "admin"}:
        raise HTTPException(status_code=403, detail="Only technicians can update ticket status.")
    ticket = db.get(ServiceTicket, ticket_id)
    if ticket is None or not ticket.requires_technician:
        raise HTTPException(status_code=404, detail="Service ticket not found.")
    if user.district and user.role != "admin" and ticket.district != user.district:
        raise HTTPException(status_code=403, detail="This ticket is outside your assigned district.")
    if user.sector and user.role != "admin" and ticket.sector != user.sector:
        raise HTTPException(status_code=403, detail="This ticket is outside your assigned sector.")

    previous_status = ticket.status
    ticket.status = payload.status
    db.add(
        AuditLog(
            ticket_id=ticket.id,
            actor_user_id=user.id,
            event_type="TICKET_STATUS_UPDATED",
            details={
                "from": previous_status,
                "to": payload.status,
                "note": payload.note.strip() if payload.note else None,
            },
        )
    )
    db.commit()
    db.refresh(ticket)
    return ticket
