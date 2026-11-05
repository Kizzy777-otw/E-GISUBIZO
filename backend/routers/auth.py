"""Authentication helpers for technician and administrator endpoints."""

from hashlib import sha256
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import UserResponse

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
bearer_scheme = HTTPBearer(auto_error=False)
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
    if user is None or not secrets.compare_digest(user.token_hash, token_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The supplied access token is not valid.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


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
