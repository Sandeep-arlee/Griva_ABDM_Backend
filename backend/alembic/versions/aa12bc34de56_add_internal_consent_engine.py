"""add internal consent engine tables

Revision ID: aa12bc34de56
Revises: 9f7c2d1e3b42
Create Date: 2026-02-17 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "aa12bc34de56"
down_revision = "9f7c2d1e3b42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "internal_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_patient_id", sa.String(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="GRANTED"),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
    )
    op.create_index("ix_internal_consents_tenant_id", "internal_consents", ["tenant_id"])
    op.create_index(
        "ix_internal_consents_tenant_id_patient_purpose",
        "internal_consents",
        ["tenant_id", "subject_patient_id", "purpose"],
        unique=True,
    )

    op.create_table(
        "consent_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("internal_consent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("granted_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", postgresql.JSONB(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["internal_consent_id"], ["internal_consents.id"]),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"]),
    )
    op.create_index("ix_consent_grants_tenant_id", "consent_grants", ["tenant_id"])
    op.create_index("ix_consent_grants_internal_consent_id", "consent_grants", ["internal_consent_id"])

    op.create_table(
        "consent_revocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("internal_consent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revoked_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("meta", postgresql.JSONB(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["internal_consent_id"], ["internal_consents.id"]),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"]),
    )
    op.create_index("ix_consent_revocations_tenant_id", "consent_revocations", ["tenant_id"])
    op.create_index("ix_consent_revocations_internal_consent_id", "consent_revocations", ["internal_consent_id"])


def downgrade() -> None:
    op.drop_index("ix_consent_revocations_internal_consent_id", table_name="consent_revocations")
    op.drop_index("ix_consent_revocations_tenant_id", table_name="consent_revocations")
    op.drop_table("consent_revocations")

    op.drop_index("ix_consent_grants_internal_consent_id", table_name="consent_grants")
    op.drop_index("ix_consent_grants_tenant_id", table_name="consent_grants")
    op.drop_table("consent_grants")

    op.drop_index("ix_internal_consents_tenant_id_patient_purpose", table_name="internal_consents")
    op.drop_index("ix_internal_consents_tenant_id", table_name="internal_consents")
    op.drop_table("internal_consents")
