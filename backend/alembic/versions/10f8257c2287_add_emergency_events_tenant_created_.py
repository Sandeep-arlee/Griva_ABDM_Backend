"""add emergency events tenant_created index

Revision ID: 10f8257c2287
Revises: e1f2a3b4c5d6
Create Date: 2026-02-24 15:30:07.135798

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10f8257c2287'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_emergency_events_v2_tenant_created_desc
        ON emergency_access_events_v2 (tenant_id, created_at DESC, id DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_emergency_events_v2_tenant_created_desc")
