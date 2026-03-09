"""add idempotency keys table

Revision ID: 8c4b3f1d2e9a
Revises: 730ef072bea7
Create Date: 2026-03-09 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8c4b3f1d2e9a"
down_revision: Union[str, None] = "730ef072bea7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("response_hash", sa.String(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.UniqueConstraint("request_id", name="uq_idempotency_request_id"),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
