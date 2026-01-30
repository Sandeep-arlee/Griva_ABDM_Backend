"""initial schema

Revision ID: 0001_init
Revises:
Create Date: 2026-01-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None

# Define enum ONCE — no manual create()
consent_status = sa.Enum(
    "REQUESTED",
    "GRANTED",
    "REVOKED",
    "EXPIRED",
    "DENIED",
    name="consent_status",
)


def upgrade() -> None:
    op.create_table(
        "consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("abdm_consent_id", sa.String(), nullable=False),
        sa.Column("patient_id", sa.String(), nullable=False),
        sa.Column("hiu_id", sa.String(), nullable=False),
        sa.Column("hip_id", sa.String(), nullable=False),
        sa.Column("status", consent_status, nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_consents_abdm_consent_id", "consents", ["abdm_consent_id"], unique=True)
    op.create_index("ix_consents_patient_id", "consents", ["patient_id"])

    op.create_table(
        "consent_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("consent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", consent_status, nullable=False),
        sa.Column("event_payload", postgresql.JSONB(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["consent_id"], ["consents.id"]),
    )

    op.create_table(
        "medical_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("patient_id", sa.String(), nullable=False),
        sa.Column("record_type", sa.String(), nullable=False),
        sa.Column("uri", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_medical_records_patient_id", "medical_records", ["patient_id"])


    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_medical_records_patient_id", table_name="medical_records")
    op.drop_table("medical_records")

    op.drop_table("consent_events")

    op.drop_index("ix_consents_patient_id", table_name="consents")
    op.drop_index("ix_consents_abdm_consent_id", table_name="consents")
    op.drop_table("consents")

    # Optional but safe in first migration
    consent_status.drop(op.get_bind(), checkfirst=True)
