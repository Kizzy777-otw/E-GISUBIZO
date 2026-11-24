"""Add optional customer phone to service tickets.

Revision ID: 0005_customer_phone
Revises: 0004_hardware_installation_metadata
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_customer_phone"
down_revision = "0004_hardware_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("service_tickets", sa.Column("customer_phone", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("service_tickets", "customer_phone")
