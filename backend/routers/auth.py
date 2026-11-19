"""Authentication helpers for technician and administrator endpoints."""

from datetime import timedelta
from hashlib import sha256
import secrets
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuthSession, User, utc_now
from ..schemas import PasswordLoginRequest, PasswordLoginResponse, UserResponse

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
bearer_scheme = HTTPBearer(auto_error=False)
password_hasher = PasswordHasher()
DatabaseSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DatabaseSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Technician or administrator sign-in is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Resolve bearer tokens by hash so the original secret is never persisted.
    token_hash = sha256(credentials.credentials.encode("utf-8")).hexdigest()
    user = db.scalar(select(User).where(User.token_hash == token_hash, User.active.is_(True)))
    if user is None:
        session = db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == token_hash,
                AuthSession.expires_at > utc_now(),
            )
        )
        if session is not None:
            user = db.scalar(select(User).where(User.id == session.user_id, User.active.is_(True)))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The supplied access token is not valid.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.post("/login", response_model=PasswordLoginResponse)
def login_with_password(payload: PasswordLoginRequest, db: DatabaseSession) -> PasswordLoginResponse:
    user = db.scalar(select(User).where(User.username == payload.username.strip(), User.active.is_(True)))
    if user is None or not user.password_hash:
        raise HTTPException(status_code=401, detail="The username or password is incorrect.")
    try:
        password_hasher.verify(user.password_hash, payload.password)
    except (VerifyMismatchError, ValueError):
        raise HTTPException(status_code=401, detail="The username or password is incorrect.")

    access_token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=sha256(access_token.encode("utf-8")).hexdigest(),
            expires_at=utc_now() + timedelta(hours=24),
        )
    )
    db.commit()
    db.refresh(user)
    return PasswordLoginResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.post("/logout")
def logout(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DatabaseSession,
) -> dict[str, str]:
    if credentials is not None:
        token_hash = sha256(credentials.credentials.encode("utf-8")).hexdigest()
        session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))
        if session is not None:
            db.delete(session)
            db.commit()
    return {"status": "logged_out"}


@router.get("/me", response_model=UserResponse)
def current_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


def require_role(*allowed_roles: str):
    """Build a dependency that rejects authenticated users outside the allowed roles."""
    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is not permitted to perform this action.",
            )
        return user

    return dependency
