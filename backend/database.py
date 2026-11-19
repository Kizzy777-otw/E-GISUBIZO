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
elif DATABASE_URL.startswith("postgresql"):
    # Keep per-function connection use bounded; prefer Neon's pooled URL at runtime.
    pool_size = int(os.getenv("DB_POOL_SIZE", "2"))
    if not 1 <= pool_size <= 10:
        raise RuntimeError("DB_POOL_SIZE must be an integer between 1 and 10.")
    _engine_options.update(
        pool_size=pool_size,
        max_overflow=0,
        pool_timeout=10,
    )

engine = create_engine(DATABASE_URL, **_engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def validate_database_configuration() -> None:
    """Prevent production/serverless instances from silently using ephemeral SQLite."""
    is_deployed = os.getenv("APP_ENV", "").lower() in {"staging", "production"} or os.getenv("VERCEL") == "1"
    if is_deployed and engine.dialect.name == "sqlite":
        raise RuntimeError(
            "Production and Vercel deployments require a persistent PostgreSQL DATABASE_URL; "
            "SQLite storage on a function filesystem is ephemeral."
        )


def should_create_schema() -> bool:
    """Allow metadata creation only for local/test runs, never as a deployed migration."""
    is_deployed = os.getenv("APP_ENV", "").lower() in {"staging", "production"} or os.getenv("VERCEL") == "1"
    setting = os.getenv("DB_AUTO_CREATE")
    if setting is not None and setting.lower() not in {"1", "true", "yes", "0", "false", "no"}:
        raise RuntimeError("DB_AUTO_CREATE must be set to true or false.")
    if is_deployed and setting is not None and setting.lower() in {"1", "true", "yes"}:
        raise RuntimeError("DB_AUTO_CREATE must be disabled on deployed environments; use Alembic.")
    if is_deployed:
        return False
    if setting is not None:
        return setting.lower() in {"1", "true", "yes"}
    return True


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped session and close it even when a request fails."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
