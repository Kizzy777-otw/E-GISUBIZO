"""Database engine and session configuration."""

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./egisubizo.db")
_engine_options: dict[str, object] = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    # SQLite's test server and request handlers use separate worker threads.
    _engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def validate_database_configuration() -> None:
    """Prevent production/serverless instances from silently using ephemeral SQLite."""
    is_deployed = os.getenv("APP_ENV", "").lower() == "production" or os.getenv("VERCEL") == "1"
    if is_deployed and engine.dialect.name == "sqlite":
        raise RuntimeError(
            "Production and Vercel deployments require a persistent PostgreSQL DATABASE_URL; "
            "SQLite storage on a function filesystem is ephemeral."
        )


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped session and close it even when a request fails."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
