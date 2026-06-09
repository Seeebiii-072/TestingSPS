"""Initial SPS SecureDesk schema.

Revision ID: 202606090001
Revises:
Create Date: 2026-06-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202606090001"
down_revision = None
branch_labels = None
depends_on = None


def _uuid_default():
    bind = op.get_bind()
    return sa.func.gen_random_uuid() if bind.dialect.name == "postgresql" else None


def _jsonb_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    uuid_default = _uuid_default()
    user_role = sa.Enum(
        "intern",
        "employee",
        "agent",
        "security_admin",
        "manager",
        "administrator",
        name="user_role",
        native_enum=False,
        create_constraint=True,
    )
    ticket_source = sa.Enum("email", "portal_form", "chat", name="ticket_source", native_enum=False, create_constraint=True)
    ticket_category = sa.Enum(
        "cloud",
        "cybersecurity",
        "identity_access",
        "devops",
        "internship_hr",
        "general_it",
        name="ticket_category",
        native_enum=False,
        create_constraint=True,
    )
    ticket_priority = sa.Enum("low", "medium", "high", "critical", name="ticket_priority", native_enum=False, create_constraint=True)
    risk_level = sa.Enum("standard", "high", name="risk_level", native_enum=False, create_constraint=True)
    ticket_team = sa.Enum("it", "security", "devops", "hr", "management", name="ticket_team", native_enum=False, create_constraint=True)
    ticket_status = sa.Enum(
        "open",
        "in_progress",
        "waiting_approval",
        "waiting_user",
        "resolved",
        "closed",
        name="ticket_status",
        native_enum=False,
        create_constraint=True,
    )
    timeline_event_type = sa.Enum(
        "ticket_created",
        "email_received",
        "agent_reply_portal",
        "agent_reply_email",
        "internal_note",
        "status_change",
        "field_update",
        "approval_requested",
        "approval_resolved",
        "file_uploaded",
        "chat_escalation",
        "ai_classified",
        name="timeline_event_type",
        native_enum=False,
        create_constraint=True,
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=uuid_default),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=uuid_default),
        sa.Column("ticket_number", sa.String(length=20), nullable=False),
        sa.Column("source", ticket_source, nullable=False),
        sa.Column("requester_id", sa.Uuid(), nullable=True),
        sa.Column("requester_email", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", ticket_category, nullable=False),
        sa.Column("priority", ticket_priority, nullable=False),
        sa.Column("risk_level", risk_level, nullable=False),
        sa.Column("team", ticket_team, nullable=False),
        sa.Column("status", ticket_status, nullable=False),
        sa.Column("assigned_agent_id", sa.Uuid(), nullable=True),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["assigned_agent_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"]),
        sa.UniqueConstraint("ticket_number"),
    )
    op.create_index("ix_tickets_assigned_agent_id", "tickets", ["assigned_agent_id"])
    op.create_index("ix_tickets_requester_email", "tickets", ["requester_email"])
    op.create_index("ix_tickets_requester_id", "tickets", ["requester_id"])
    op.create_index("ix_tickets_ticket_number", "tickets", ["ticket_number"])

    op.create_table(
        "timeline_events",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=uuid_default),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", timeline_event_type, nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("channel", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_timeline_events_ticket_id", "timeline_events", ["ticket_id"])

    op.create_table(
        "attachments",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=uuid_default),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
    )
    op.create_index("ix_attachments_ticket_id", "attachments", ["ticket_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=uuid_default),
        sa.Column("ticket_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("details", _jsonb_type(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_index("ix_attachments_ticket_id", table_name="attachments")
    op.drop_table("attachments")
    op.drop_index("ix_timeline_events_ticket_id", table_name="timeline_events")
    op.drop_table("timeline_events")
    op.drop_index("ix_tickets_ticket_number", table_name="tickets")
    op.drop_index("ix_tickets_requester_id", table_name="tickets")
    op.drop_index("ix_tickets_requester_email", table_name="tickets")
    op.drop_index("ix_tickets_assigned_agent_id", table_name="tickets")
    op.drop_table("tickets")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
