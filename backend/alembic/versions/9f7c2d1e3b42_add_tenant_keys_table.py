"""add tenant_keys table

Revision ID: 9f7c2d1e3b42
Revises: 8c2f3a5b9d01
Create Date: 2026-02-17 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "9f7c2d1e3b42"
down_revision = "8c2f3a5b9d01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("encrypted_dek", sa.String(), nullable=False),
        sa.Column("key_version", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
    )
    op.create_index("ix_tenant_keys_tenant_id", "tenant_keys", ["tenant_id"])
    op.create_index("ix_tenant_keys_tenant_id_active", "tenant_keys", ["tenant_id", "is_active"])


def downgrade() -> None:
    op.drop_index("ix_tenant_keys_tenant_id_active", table_name="tenant_keys")
    op.drop_index("ix_tenant_keys_tenant_id", table_name="tenant_keys")
    op.drop_table("tenant_keys")
