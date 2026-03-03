"""add emergency access sessions

Revision ID: b7d6c1a2e8f9
Revises: aa12bc34de56
Create Date: 2026-02-20 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b7d6c1a2e8f9"
down_revision = "aa12bc34de56"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "emergency_access_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("super_admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["super_admin_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.CheckConstraint("expires_at > created_at", name="ck_emergency_access_sessions_expires_after_created"),
    )
    op.create_index(
        "ix_emergency_access_sessions_tenant_admin_expires",
        "emergency_access_sessions",
        ["tenant_id", "super_admin_id", "expires_at"],
    )
    op.create_index(
        "ix_emergency_access_sessions_expires_at",
        "emergency_access_sessions",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_emergency_access_sessions_expires_at", table_name="emergency_access_sessions")
    op.drop_index("ix_emergency_access_sessions_tenant_admin_expires", table_name="emergency_access_sessions")
    op.drop_table("emergency_access_sessions")
