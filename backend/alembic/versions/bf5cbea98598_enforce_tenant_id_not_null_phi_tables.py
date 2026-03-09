"""enforce_tenant_id_not_null_phi_tables

Revision ID: bf5cbea98598
Revises: 8c4b3f1d2e9a
Create Date: 2026-03-09 12:23:56.317514

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bf5cbea98598'
down_revision: Union[str, None] = '8c4b3f1d2e9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE consents c
        SET tenant_id = p.tenant_id
        FROM patients p
        WHERE c.patient_id = p.patient_id
          AND c.tenant_id IS NULL;
        """
    )
    op.execute(
        """
        UPDATE medical_records m
        SET tenant_id = p.tenant_id
        FROM patients p
        WHERE m.patient_id = p.patient_id
          AND m.tenant_id IS NULL;
        """
    )
    op.execute(
        """
        UPDATE health_information_requests r
        SET tenant_id = c.tenant_id
        FROM consents c
        WHERE r.consent_id = c.id
          AND r.tenant_id IS NULL;
        """
    )
    op.execute(
        """
        UPDATE health_information_events e
        SET tenant_id = r.tenant_id
        FROM health_information_requests r
        WHERE e.health_information_request_id = r.id
          AND e.tenant_id IS NULL;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM consents WHERE tenant_id IS NULL) THEN
                RAISE EXCEPTION 'consents tenant_id backfill incomplete';
            END IF;
            IF EXISTS (SELECT 1 FROM medical_records WHERE tenant_id IS NULL) THEN
                RAISE EXCEPTION 'medical_records tenant_id backfill incomplete';
            END IF;
            IF EXISTS (SELECT 1 FROM health_information_requests WHERE tenant_id IS NULL) THEN
                RAISE EXCEPTION 'health_information_requests tenant_id backfill incomplete';
            END IF;
            IF EXISTS (SELECT 1 FROM health_information_events WHERE tenant_id IS NULL) THEN
                RAISE EXCEPTION 'health_information_events tenant_id backfill incomplete';
            END IF;
        END;
        $$;
        """
    )

    op.alter_column("consents", "tenant_id", nullable=False)
    op.alter_column("medical_records", "tenant_id", nullable=False)
    op.alter_column("health_information_requests", "tenant_id", nullable=False)
    op.alter_column("health_information_events", "tenant_id", nullable=False)

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_consents_tenant_id ON consents (tenant_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_medical_records_tenant_id ON medical_records (tenant_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_hi_requests_tenant_id ON health_information_requests (tenant_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_hi_events_tenant_id ON health_information_events (tenant_id);"
    )


def downgrade() -> None:
    op.alter_column("health_information_events", "tenant_id", nullable=True)
    op.alter_column("health_information_requests", "tenant_id", nullable=True)
    op.alter_column("medical_records", "tenant_id", nullable=True)
    op.alter_column("consents", "tenant_id", nullable=True)
