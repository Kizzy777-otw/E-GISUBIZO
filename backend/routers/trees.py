"""Public decision-tree reads and administrator tree editing."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, DiagnosticTree, User, utc_now
from ..schemas import DiagnosticTreeResponse, DiagnosticTreeUpdate
from .auth import require_role

router = APIRouter(prefix="/api/v1/diagnostic-trees", tags=["diagnostic trees"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[DiagnosticTreeResponse])
def list_trees(db: DatabaseSession) -> list[DiagnosticTree]:
    # Clients cache the active database records, not a separately hard-coded UI tree.
    return list(
        db.scalars(
            select(DiagnosticTree)
            .where(DiagnosticTree.active.is_(True))
            .order_by(DiagnosticTree.appliance_type, DiagnosticTree.slug)
        ).all()
    )


@router.put("/{slug}", response_model=DiagnosticTreeResponse)
def update_tree(
    slug: str,
    payload: DiagnosticTreeUpdate,
    db: DatabaseSession,
    admin: Annotated[User, Depends(require_role("admin"))],
) -> DiagnosticTree:
    # The administrator can revise diagnostic content without rebuilding the PWA.
    tree = db.scalar(select(DiagnosticTree).where(DiagnosticTree.slug == slug))
    if tree is None:
        raise HTTPException(status_code=404, detail="Diagnostic tree not found.")
    tree.appliance_type = payload.appliance_type
    tree.version = payload.version
    tree.content = payload.content
    tree.active = payload.active
    tree.updated_at = utc_now()
    db.add(
        AuditLog(
            actor_user_id=admin.id,
            event_type="DIAGNOSTIC_TREE_UPDATED",
            details={"slug": slug, "version": payload.version, "active": payload.active},
        )
    )
    db.commit()
    db.refresh(tree)
    return tree
