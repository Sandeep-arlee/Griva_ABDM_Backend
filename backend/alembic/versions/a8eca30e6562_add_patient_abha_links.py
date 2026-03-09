"""add_patient_abha_links

Revision ID: a8eca30e6562
Revises: c578654dbb81
Create Date: 2026-03-03 17:06:23.009037

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a8eca30e6562'
down_revision: Union[str, None] = 'c578654dbb81'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patient_abha_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("abha_address_enc", sa.JSON(), nullable=True),
        sa.Column("abha_number_enc", sa.JSON(), nullable=True),
        sa.Column("abha_hash", sa.String(), nullable=False),
        sa.Column("link_status", sa.String(), nullable=False, server_default="VERIFIED"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
    )
    op.create_index(
        "ix_abha_links_tenant_hash",
        "patient_abha_links",
        ["tenant_id", "abha_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_abha_links_tenant_hash", table_name="patient_abha_links")
    op.drop_table("patient_abha_links")
