"""Read-only audit history for administrators."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, User
from ..schemas import AuditLogResponse
from .auth import require_role

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[AuditLogResponse])
def list_audit_logs(
    db: DatabaseSession,
    _admin: Annotated[User, Depends(require_role("admin"))],
) -> list[AuditLog]:
    return list(
        db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()))
        .all()
    )
