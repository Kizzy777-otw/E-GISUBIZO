"""Add real installation metadata to hardware units.

Revision ID: 0004_hardware_metadata
Revises: 0003_auth_sessions
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_hardware_metadata"
down_revision = "0003_auth_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("hardware_units", sa.Column("account_name", sa.String(length=160), nullable=True))
    op.add_column("hardware_units", sa.Column("owner_name", sa.String(length=160), nullable=True))
    op.add_column("hardware_units", sa.Column("hub", sa.String(length=160), nullable=True))
    op.add_column("hardware_units", sa.Column("county", sa.String(length=120), nullable=True))
    op.add_column("hardware_units", sa.Column("constituency", sa.String(length=120), nullable=True))
    op.add_column("hardware_units", sa.Column("village", sa.String(length=120), nullable=True))
    op.add_column("hardware_units", sa.Column("appraisal_status", sa.String(length=40), nullable=True))
    op.add_column("hardware_units", sa.Column("commissioning_status", sa.String(length=40), nullable=True))
    op.add_column("hardware_units", sa.Column("contract_status", sa.String(length=40), nullable=True))
    op.add_column("hardware_units", sa.Column("payment_format", sa.String(length=40), nullable=True))
    op.add_column("hardware_units", sa.Column("lead_source", sa.String(length=100), nullable=True))
    op.add_column("hardware_units", sa.Column("sales_person", sa.String(length=160), nullable=True))
    op.add_column("hardware_units", sa.Column("installation_year", sa.String(length=7), nullable=True))
    op.add_column("hardware_units", sa.Column("source_reported_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for column in (
        "source_reported_at",
        "installation_year",
        "sales_person",
        "lead_source",
        "payment_format",
        "contract_status",
        "commissioning_status",
        "appraisal_status",
        "village",
        "constituency",
        "county",
        "hub",
        "owner_name",
        "account_name",
    ):
        op.drop_column("hardware_units", column)
