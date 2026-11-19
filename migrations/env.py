from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from backend.database import Base
from backend import models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = (
    os.getenv("DATABASE_MIGRATION_URL")
    or os.getenv("DATABASE_URL_UNPOOLED")
    or os.getenv("DATABASE_URL")
)
if not database_url:
    raise RuntimeError(
        "Set DATABASE_MIGRATION_URL or DATABASE_URL_UNPOOLED to a direct PostgreSQL connection."
    )

url = make_url(database_url)
if url.get_backend_name() != "postgresql":
    if os.getenv("APP_ENV", "").lower() == "production":
        raise RuntimeError("Production migrations require PostgreSQL, not the test or local database.")
elif "-pooler" in (url.host or ""):
    raise RuntimeError("Alembic requires a direct PostgreSQL URL; pooled Neon URLs are not supported.")

config.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
