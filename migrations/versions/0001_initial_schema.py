"""Create the initial E-Gisubizo schema.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("district", sa.String(length=100), nullable=True),
        sa.Column("sector", sa.String(length=100), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_token_hash", "users", ["token_hash"], unique=True)

    op.create_table(
        "hardware_units",
        sa.Column("hardware_id", sa.String(length=80), primary_key=True),
        sa.Column("model_type", sa.String(length=20), nullable=False),
        sa.Column("district", sa.String(length=100), nullable=False),
        sa.Column("sector", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_hardware_units_model_type", "hardware_units", ["model_type"])
    op.create_index("ix_hardware_units_district", "hardware_units", ["district"])
    op.create_index("ix_hardware_units_sector", "hardware_units", ["sector"])

    op.create_table(
        "diagnostic_trees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("appliance_type", sa.String(length=20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_diagnostic_trees_slug", "diagnostic_trees", ["slug"], unique=True)
    op.create_index("ix_diagnostic_trees_appliance_type", "diagnostic_trees", ["appliance_type"])

    op.create_table(
        "service_tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_ticket_id", sa.String(length=36), nullable=False),
        sa.Column("hardware_id", sa.String(length=80), sa.ForeignKey("hardware_units.hardware_id"), nullable=False),
        sa.Column("model_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("fault_category", sa.String(length=120), nullable=False),
        sa.Column("fault_code", sa.JSON(), nullable=False),
        sa.Column("diagnostic_path", sa.JSON(), nullable=False),
        sa.Column("requires_technician", sa.Boolean(), nullable=False),
        sa.Column("district", sa.String(length=100), nullable=False),
        sa.Column("sector", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_service_tickets_client_ticket_id", "service_tickets", ["client_ticket_id"], unique=True)
    op.create_index("ix_service_tickets_hardware_id", "service_tickets", ["hardware_id"])
    op.create_index("ix_service_tickets_model_type", "service_tickets", ["model_type"])
    op.create_index("ix_service_tickets_status", "service_tickets", ["status"])
    op.create_index("ix_service_tickets_priority", "service_tickets", ["priority"])
    op.create_index("ix_service_tickets_fault_category", "service_tickets", ["fault_category"])
    op.create_index("ix_service_tickets_requires_technician", "service_tickets", ["requires_technician"])
    op.create_index("ix_service_tickets_district", "service_tickets", ["district"])
    op.create_index("ix_service_tickets_sector", "service_tickets", ["sector"])
    op.create_index("ix_service_tickets_created_at", "service_tickets", ["created_at"])
    op.create_index("ix_service_tickets_status_priority", "service_tickets", ["status", "priority"])
    op.create_index("ix_service_tickets_zone", "service_tickets", ["district", "sector"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("service_tickets.id"), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_ticket_id", "audit_logs", ["ticket_id"])
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION reject_audit_log_mutation() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit log rows are immutable';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            """
            CREATE TRIGGER audit_logs_immutable
            BEFORE UPDATE OR DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation()
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_logs_immutable ON audit_logs")
        op.execute("DROP FUNCTION IF EXISTS reject_audit_log_mutation()")
    op.drop_table("audit_logs")
    op.drop_table("service_tickets")
    op.drop_table("diagnostic_trees")
    op.drop_table("hardware_units")
    op.drop_table("users")
