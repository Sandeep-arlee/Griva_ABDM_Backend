"""add tenants and tenant_id columns

Revision ID: 8c2f3a5b9d01
Revises: 5d2c7b9c1e2f
Create Date: 2026-02-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "8c2f3a5b9d01"
down_revision = "5d2c7b9c1e2f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_tenants_name", "tenants", ["name"], unique=True)

    op.add_column("users", sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_users_tenant_id", "users", "tenants", ["tenant_id"], ["id"])
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_tenant_id_email", "users", ["tenant_id", "email"])

    op.add_column("patients", sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_patients_tenant_id", "patients", "tenants", ["tenant_id"], ["id"])
    op.create_index("ix_patients_tenant_id", "patients", ["tenant_id"])
    op.create_index("ix_patients_tenant_id_patient_id", "patients", ["tenant_id", "patient_id"])

    op.add_column("consents", sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_consents_tenant_id", "consents", "tenants", ["tenant_id"], ["id"])
    op.create_index("ix_consents_tenant_id", "consents", ["tenant_id"])
    op.create_index(
        "ix_consents_tenant_id_abdm_consent_id",
        "consents",
        ["tenant_id", "abdm_consent_id"],
    )

    op.add_column("consent_events", sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_consent_events_tenant_id", "consent_events", "tenants", ["tenant_id"], ["id"])
    op.create_index("ix_consent_events_tenant_id", "consent_events", ["tenant_id"])
    op.create_index(
        "ix_consent_events_tenant_id_consent_id",
        "consent_events",
        ["tenant_id", "consent_id"],
    )

    op.add_column("medical_records", sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_medical_records_tenant_id", "medical_records", "tenants", ["tenant_id"], ["id"])
    op.create_index("ix_medical_records_tenant_id", "medical_records", ["tenant_id"])
    op.create_index(
        "ix_medical_records_tenant_id_patient_id",
        "medical_records",
        ["tenant_id", "patient_id"],
    )

    op.add_column("audit_logs", sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_audit_logs_tenant_id", "audit_logs", "tenants", ["tenant_id"], ["id"])
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_tenant_id_request_id", "audit_logs", ["tenant_id", "request_id"])

    op.add_column("health_information_requests", sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_hi_requests_tenant_id",
        "health_information_requests",
        "tenants",
        ["tenant_id"],
        ["id"],
    )
    op.create_index("ix_hi_requests_tenant_id", "health_information_requests", ["tenant_id"])
    op.create_index(
        "ix_hi_requests_tenant_id_request_id",
        "health_information_requests",
        ["tenant_id", "request_id"],
    )

    op.add_column("health_information_events", sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_hi_events_tenant_id",
        "health_information_events",
        "tenants",
        ["tenant_id"],
        ["id"],
    )
    op.create_index("ix_hi_events_tenant_id", "health_information_events", ["tenant_id"])
    op.create_index(
        "ix_hi_events_tenant_id_request_id",
        "health_information_events",
        ["tenant_id", "health_information_request_id"],
    )

    op.add_column("trusted_requests", sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_trusted_requests_tenant_id",
        "trusted_requests",
        "tenants",
        ["tenant_id"],
        ["id"],
    )
    op.create_index("ix_trusted_requests_tenant_id", "trusted_requests", ["tenant_id"])
    op.create_index(
        "ix_trusted_requests_tenant_id_request_id",
        "trusted_requests",
        ["tenant_id", "request_id"],
    )

    op.add_column("trusted_keys", sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_trusted_keys_tenant_id",
        "trusted_keys",
        "tenants",
        ["tenant_id"],
        ["id"],
    )
    op.create_index("ix_trusted_keys_tenant_id", "trusted_keys", ["tenant_id"])
    op.create_index("ix_trusted_keys_tenant_id_key_id", "trusted_keys", ["tenant_id", "key_id"])


def downgrade() -> None:
    op.drop_index("ix_trusted_keys_tenant_id_key_id", table_name="trusted_keys")
    op.drop_index("ix_trusted_keys_tenant_id", table_name="trusted_keys")
    op.drop_constraint("fk_trusted_keys_tenant_id", "trusted_keys", type_="foreignkey")
    op.drop_column("trusted_keys", "tenant_id")

    op.drop_index("ix_trusted_requests_tenant_id_request_id", table_name="trusted_requests")
    op.drop_index("ix_trusted_requests_tenant_id", table_name="trusted_requests")
    op.drop_constraint("fk_trusted_requests_tenant_id", "trusted_requests", type_="foreignkey")
    op.drop_column("trusted_requests", "tenant_id")

    op.drop_index("ix_hi_events_tenant_id_request_id", table_name="health_information_events")
    op.drop_index("ix_hi_events_tenant_id", table_name="health_information_events")
    op.drop_constraint("fk_hi_events_tenant_id", "health_information_events", type_="foreignkey")
    op.drop_column("health_information_events", "tenant_id")

    op.drop_index("ix_hi_requests_tenant_id_request_id", table_name="health_information_requests")
    op.drop_index("ix_hi_requests_tenant_id", table_name="health_information_requests")
    op.drop_constraint("fk_hi_requests_tenant_id", "health_information_requests", type_="foreignkey")
    op.drop_column("health_information_requests", "tenant_id")

    op.drop_index("ix_audit_logs_tenant_id_request_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_id", table_name="audit_logs")
    op.drop_constraint("fk_audit_logs_tenant_id", "audit_logs", type_="foreignkey")
    op.drop_column("audit_logs", "tenant_id")

    op.drop_index("ix_medical_records_tenant_id_patient_id", table_name="medical_records")
    op.drop_index("ix_medical_records_tenant_id", table_name="medical_records")
    op.drop_constraint("fk_medical_records_tenant_id", "medical_records", type_="foreignkey")
    op.drop_column("medical_records", "tenant_id")

    op.drop_index("ix_consent_events_tenant_id_consent_id", table_name="consent_events")
    op.drop_index("ix_consent_events_tenant_id", table_name="consent_events")
    op.drop_constraint("fk_consent_events_tenant_id", "consent_events", type_="foreignkey")
    op.drop_column("consent_events", "tenant_id")

    op.drop_index("ix_consents_tenant_id_abdm_consent_id", table_name="consents")
    op.drop_index("ix_consents_tenant_id", table_name="consents")
    op.drop_constraint("fk_consents_tenant_id", "consents", type_="foreignkey")
    op.drop_column("consents", "tenant_id")

    op.drop_index("ix_patients_tenant_id_patient_id", table_name="patients")
    op.drop_index("ix_patients_tenant_id", table_name="patients")
    op.drop_constraint("fk_patients_tenant_id", "patients", type_="foreignkey")
    op.drop_column("patients", "tenant_id")

    op.drop_index("ix_users_tenant_id_email", table_name="users")
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_constraint("fk_users_tenant_id", "users", type_="foreignkey")
    op.drop_column("users", "tenant_id")

    op.drop_index("ix_tenants_name", table_name="tenants")
    op.drop_table("tenants")
