"""add trusted_keys and trusted_requests tables

Revision ID: 5d2c7b9c1e2f
Revises: 4b1c8a9b7f1b
Create Date: 2026-02-11 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "5d2c7b9c1e2f"
down_revision = "4b1c8a9b7f1b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trusted_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("key_id", sa.String(), nullable=False),
        sa.Column("public_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_trusted_keys_key_id", "trusted_keys", ["key_id"], unique=True)

    op.create_table(
        "trusted_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("signature", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_trusted_requests_request_id_signature",
        "trusted_requests",
        ["request_id", "signature"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_trusted_requests_request_id_signature", table_name="trusted_requests")
    op.drop_table("trusted_requests")

    op.drop_index("ix_trusted_keys_key_id", table_name="trusted_keys")
    op.drop_table("trusted_keys")
