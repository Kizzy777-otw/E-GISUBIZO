"""Shared server-side actions for audit and mocked dispatch notifications."""

import logging

from sqlalchemy.orm import Session

from .models import AuditLog, ServiceTicket

logger = logging.getLogger("egisubizo.notifications")


def log_mock_sms_notification(db: Session, ticket: ServiceTicket) -> None:
    """Record a mock dispatch notification without contacting an SMS provider."""
    # Keep the pilot side-effect observable without sending real messages or exposing phone data.
    message = (
        f"Mock SMS dispatch: ticket={ticket.id}, hardware={ticket.hardware_id}, "
        f"fault={ticket.fault_code['code']}, district={ticket.district}, sector={ticket.sector}"
    )
    logger.info(message)
    db.add(
        AuditLog(
            ticket_id=ticket.id,
            event_type="MOCK_SMS_TRIGGERED",
            details={"channel": "mock_sms", "message": message},
        )
    )
