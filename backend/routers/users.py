"""Administrator endpoints for issuing and revoking user access."""

from hashlib import sha256
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, User
from ..schemas import UserAccessUpdate, UserCreateRequest, UserCreatedResponse, UserResponse
from .auth import require_role

router = APIRouter(prefix="/api/v1/users", tags=["users"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[UserResponse])
def list_users(
    db: DatabaseSession,
    _admin: Annotated[User, Depends(require_role("admin"))],
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.username)).all())


@router.post("", response_model=UserCreatedResponse, status_code=201)
def create_user(
    payload: UserCreateRequest,
    db: DatabaseSession,
    admin: Annotated[User, Depends(require_role("admin"))],
) -> UserCreatedResponse:
    if db.scalar(select(User).where(User.username == payload.username)) is not None:
        raise HTTPException(status_code=409, detail="That username is already in use.")

    # Generate the credential server-side and return its plaintext only in this response.
    access_token = secrets.token_urlsafe(32)
    user = User(
        username=payload.username,
        role=payload.role,
        token_hash=sha256(access_token.encode("utf-8")).hexdigest(),
        district=payload.district,
        sector=payload.sector,
        active=True,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="That username or token is already in use.") from error
    db.add(
        AuditLog(
            actor_user_id=admin.id,
            event_type="USER_ACCESS_CREATED",
            details={
                "username": user.username,
                "role": user.role,
                "district": user.district,
                "sector": user.sector,
            },
        )
    )
    db.commit()
    db.refresh(user)
    return UserCreatedResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        district=user.district,
        sector=user.sector,
        active=user.active,
        access_token=access_token,
    )


@router.patch("/{user_id}/access", response_model=UserResponse)
def update_user_access(
    user_id: int,
    payload: UserAccessUpdate,
    db: DatabaseSession,
    admin: Annotated[User, Depends(require_role("admin"))],
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == admin.id and not payload.active:
        raise HTTPException(status_code=422, detail="You cannot revoke your own administrator access.")

    # Revocation takes effect on the next request because every token is checked in the DB.
    previous_active = user.active
    user.active = payload.active
    db.add(
        AuditLog(
            actor_user_id=admin.id,
            event_type="USER_ACCESS_UPDATED",
            details={
                "username": user.username,
                "active_from": previous_active,
                "active_to": user.active,
            },
        )
    )
    db.commit()
    db.refresh(user)
    return user
