"""enforce_not_null_tenant_id_on_domain_tables

Revision ID: 4e137715189a
Revises: 11a2b3c4d5e6
Create Date: 2026-02-27 14:15:57.581215

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e137715189a'
down_revision: Union[str, None] = '11a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("consents", "tenant_id", nullable=False)
    op.alter_column("health_information_requests", "tenant_id", nullable=False)
    op.alter_column("health_information_events", "tenant_id", nullable=False)
    op.alter_column("audit_logs", "tenant_id", nullable=False)
    op.alter_column("medical_records", "tenant_id", nullable=False)


def downgrade() -> None:
    op.alter_column("medical_records", "tenant_id", nullable=True)
    op.alter_column("audit_logs", "tenant_id", nullable=True)
    op.alter_column("health_information_events", "tenant_id", nullable=True)
    op.alter_column("health_information_requests", "tenant_id", nullable=True)
    op.alter_column("consents", "tenant_id", nullable=True)
