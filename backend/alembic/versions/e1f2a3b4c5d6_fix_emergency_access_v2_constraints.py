"""fix emergency access v2 constraints

Revision ID: e1f2a3b4c5d6
Revises: d4e5f6a7b8c9
Create Date: 2026-02-23 00:00:00.000000
"""
from alembic import op

revision = "e1f2a3b4c5d6"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.execute(
        "ALTER TABLE emergency_access_sessions_v2 "
        "DROP CONSTRAINT IF EXISTS emergency_no_overlap_v2"
    )
    op.execute(
        "ALTER TABLE emergency_access_sessions_v2 "
        "DROP CONSTRAINT IF EXISTS ck_emergency_access_sessions_v2_duration"
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM emergency_access_sessions_v2
                WHERE approved_at IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Phase E invariant violation: approved_at contains NULL values. Manual remediation required before enforcing NOT NULL.';
            END IF;
        END;
        $$;
        """
    )
    op.execute(
        "ALTER TABLE emergency_access_sessions_v2 "
        "ALTER COLUMN approved_at SET NOT NULL"
    )

    op.execute(
        "ALTER TABLE emergency_access_sessions_v2 "
        "ADD CONSTRAINT ck_emergency_access_sessions_v2_duration "
        "CHECK (expires_at <= approved_at + interval '60 minutes')"
    )
    op.execute(
        "ALTER TABLE emergency_access_sessions_v2 "
        "ADD CONSTRAINT ck_emergency_access_sessions_v2_time_order "
        "CHECK (expires_at > approved_at)"
    )

    op.execute(
        """
        ALTER TABLE emergency_access_sessions_v2
        ADD CONSTRAINT emergency_no_overlap_v2
        EXCLUDE USING gist (
            tenant_id WITH =,
            super_admin_id WITH =,
            tstzrange(approved_at, expires_at) WITH &&
        )
        WHERE (revoked_at IS NULL)
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_emergency_identity_update_v2()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
               OR NEW.super_admin_id IS DISTINCT FROM OLD.super_admin_id
               OR NEW.scope_type IS DISTINCT FROM OLD.scope_type
               OR NEW.scope_patient_id IS DISTINCT FROM OLD.scope_patient_id
               OR NEW.approved_at IS DISTINCT FROM OLD.approved_at
               OR NEW.expires_at IS DISTINCT FROM OLD.expires_at
               OR NEW.requested_at IS DISTINCT FROM OLD.requested_at THEN
                RAISE EXCEPTION 'Immutable emergency session identity fields cannot be updated';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_emergency_session_delete_v2()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Emergency sessions are immutable and cannot be deleted';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_no_delete_emergency_sessions_v2
        BEFORE DELETE ON emergency_access_sessions_v2
        FOR EACH ROW
        EXECUTE FUNCTION prevent_emergency_session_delete_v2();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_no_delete_emergency_sessions_v2 ON emergency_access_sessions_v2"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_emergency_session_delete_v2")
    op.execute(
        "ALTER TABLE emergency_access_sessions_v2 "
        "DROP CONSTRAINT IF EXISTS emergency_no_overlap_v2"
    )
    op.execute(
        "ALTER TABLE emergency_access_sessions_v2 "
        "DROP CONSTRAINT IF EXISTS ck_emergency_access_sessions_v2_duration"
    )
    op.execute(
        "ALTER TABLE emergency_access_sessions_v2 "
        "DROP CONSTRAINT IF EXISTS ck_emergency_access_sessions_v2_time_order"
    )
    op.execute(
        "ALTER TABLE emergency_access_sessions_v2 "
        "ALTER COLUMN approved_at DROP NOT NULL"
    )
    op.execute(
        """
        ALTER TABLE emergency_access_sessions_v2
        ADD CONSTRAINT ck_emergency_access_sessions_v2_duration
        CHECK (expires_at <= requested_at + interval '60 minutes')
        """
    )
    op.execute(
        """
        ALTER TABLE emergency_access_sessions_v2
        ADD CONSTRAINT emergency_no_overlap_v2
        EXCLUDE USING gist (
            tenant_id WITH =,
            super_admin_id WITH =,
            tstzrange(requested_at, expires_at) WITH &&
        )
        WHERE (revoked_at IS NULL)
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_emergency_identity_update_v2()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.tenant_id <> OLD.tenant_id
               OR NEW.super_admin_id <> OLD.super_admin_id
               OR NEW.requested_at <> OLD.requested_at THEN
                RAISE EXCEPTION 'Immutable emergency session identity fields cannot be updated';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
