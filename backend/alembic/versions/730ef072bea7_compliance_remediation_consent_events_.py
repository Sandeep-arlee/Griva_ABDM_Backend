"""compliance_remediation_consent_events_audit_logs_tenant_isolation

Revision ID: 730ef072bea7
Revises: a8eca30e6562
Create Date: 2026-03-09 10:42:20.010278

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '730ef072bea7'
down_revision: Union[str, None] = 'a8eca30e6562'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    consent_status = sa.Enum(
        "REQUESTED",
        "GRANTED",
        "REVOKED",
        "EXPIRED",
        "DENIED",
        name="consent_status",
        create_type=False,
    )

    op.add_column("consent_events", sa.Column("old_status", consent_status, nullable=True))
    op.add_column("consent_events", sa.Column("new_status", consent_status, nullable=True))

    op.add_column("audit_logs", sa.Column("actor", sa.String(), nullable=True))
    op.add_column("audit_logs", sa.Column("action", sa.String(), nullable=True))
    op.add_column("audit_logs", sa.Column("resource_type", sa.String(), nullable=True))
    op.add_column("audit_logs", sa.Column("resource_id", sa.String(), nullable=True))

    op.execute(
        """
        UPDATE consent_events ce
        SET old_status = COALESCE(c.status, ce.event_type),
            new_status = COALESCE(c.status, ce.event_type)
        FROM consents c
        WHERE ce.consent_id = c.id
          AND (ce.old_status IS NULL OR ce.new_status IS NULL);
        """
    )
    op.execute(
        """
        UPDATE consent_events
        SET old_status = event_type,
            new_status = event_type
        WHERE old_status IS NULL OR new_status IS NULL;
        """
    )
    op.execute(
        """
        UPDATE consent_events ce
        SET tenant_id = c.tenant_id
        FROM consents c
        WHERE ce.consent_id = c.id
          AND ce.tenant_id IS NULL;
        """
    )

    op.execute(
        """
        UPDATE patients p
        SET tenant_id = l.tenant_id
        FROM patient_abha_links l
        WHERE l.patient_id = p.id
          AND p.tenant_id IS NULL;
        """
    )
    op.execute(
        """
        UPDATE patients p
        SET tenant_id = c.tenant_id
        FROM consents c
        WHERE c.patient_id = p.patient_id
          AND p.tenant_id IS NULL;
        """
    )
    op.execute(
        """
        UPDATE patients p
        SET tenant_id = m.tenant_id
        FROM medical_records m
        WHERE m.patient_id = p.patient_id
          AND p.tenant_id IS NULL;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM consent_events
                WHERE old_status IS NULL OR new_status IS NULL
            ) THEN
                RAISE EXCEPTION 'consent_events status backfill incomplete';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM consent_events
                WHERE tenant_id IS NULL
            ) THEN
                RAISE EXCEPTION 'consent_events tenant_id backfill incomplete';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM patients
                WHERE tenant_id IS NULL
            ) THEN
                RAISE EXCEPTION 'patients tenant_id backfill incomplete';
            END IF;
        END;
        $$;
        """
    )

    op.execute(
        """
        UPDATE audit_logs
        SET actor = COALESCE(actor, 'system'),
            action = COALESCE(action, event_type),
            resource_type = COALESCE(
                resource_type,
                CASE
                    WHEN consent_id IS NOT NULL THEN 'consent'
                    WHEN request_id IS NOT NULL THEN 'request'
                    ELSE 'unknown'
                END
            ),
            resource_id = COALESCE(resource_id, consent_id, request_id, 'unknown')
        WHERE actor IS NULL
           OR action IS NULL
           OR resource_type IS NULL
           OR resource_id IS NULL;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM audit_logs
                WHERE actor IS NULL OR action IS NULL OR resource_type IS NULL OR resource_id IS NULL
            ) THEN
                RAISE EXCEPTION 'audit_logs backfill incomplete';
            END IF;
        END;
        $$;
        """
    )

    op.alter_column("consent_events", "old_status", nullable=False)
    op.alter_column("consent_events", "new_status", nullable=False)
    op.alter_column("consent_events", "tenant_id", nullable=False)
    op.alter_column("patients", "tenant_id", nullable=False)

    op.alter_column("audit_logs", "actor", nullable=False)
    op.alter_column("audit_logs", "action", nullable=False)
    op.alter_column("audit_logs", "resource_type", nullable=False)
    op.alter_column("audit_logs", "resource_id", nullable=False)


def downgrade() -> None:
    op.alter_column("audit_logs", "resource_id", nullable=True)
    op.alter_column("audit_logs", "resource_type", nullable=True)
    op.alter_column("audit_logs", "action", nullable=True)
    op.alter_column("audit_logs", "actor", nullable=True)

    op.alter_column("patients", "tenant_id", nullable=True)
    op.alter_column("consent_events", "tenant_id", nullable=True)
    op.alter_column("consent_events", "new_status", nullable=True)
    op.alter_column("consent_events", "old_status", nullable=True)

    op.drop_column("audit_logs", "resource_id")
    op.drop_column("audit_logs", "resource_type")
    op.drop_column("audit_logs", "action")
    op.drop_column("audit_logs", "actor")

    op.drop_column("consent_events", "new_status")
    op.drop_column("consent_events", "old_status")
