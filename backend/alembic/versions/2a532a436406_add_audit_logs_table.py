"""add audit_logs and patients tables

Revision ID: 2a532a436406
Revises: 0001_init
Create Date: 2026-01-28 16:16:31.541786
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "2a532a436406"
down_revision: Union[str, None] = "0001_init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("hip_id", sa.String(), nullable=True),
        sa.Column("hiu_id", sa.String(), nullable=True),
        sa.Column("cm_id", sa.String(), nullable=True),
        sa.Column("consent_id", sa.String(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("meta", postgresql.JSONB(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "patients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_patients_patient_id",
        "patients",
        ["patient_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_patients_patient_id", table_name="patients")
    op.drop_table("patients")
    op.drop_table("audit_logs")
