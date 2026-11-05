"""Authenticated endpoint for exercising the mocked SMS dispatch webhook."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ServiceTicket
from ..schemas import NotificationRequest, NotificationResponse
from ..services import log_mock_sms_notification
from .auth import require_role

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post("/sms-trigger", response_model=NotificationResponse)
def trigger_sms(
    payload: NotificationRequest,
    db: DatabaseSession,
    _user=Depends(require_role("technician", "admin")),
) -> NotificationResponse:
    # This endpoint exercises dispatch logging but deliberately has no external gateway.
    ticket = db.get(ServiceTicket, payload.ticket_id)
    if ticket is None or not ticket.requires_technician:
        raise HTTPException(status_code=404, detail="Service ticket not found.")
    log_mock_sms_notification(db, ticket)
    db.commit()
    return NotificationResponse(
        ticket_id=ticket.id,
        message="Mock SMS dispatch was written to the server log and audit history.",
    )
