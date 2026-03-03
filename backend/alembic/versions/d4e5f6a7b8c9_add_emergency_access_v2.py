"""add emergency access v2 tables

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4a5b6
Create Date: 2026-02-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d4e5f6a7b8c9"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


SESSION_SCOPE_CHECK = (
    "(scope_type = 'TENANT_WIDE' AND scope_patient_id IS NULL) "
    "OR (scope_type = 'PATIENT_SCOPED' AND scope_patient_id IS NOT NULL)"
)

EVENT_TYPE_CHECK = (
    "event_type IN ("
    "'REQUESTED','APPROVED','USED','EXPORT','DECRYPT','REVOKED','EXPIRED'"
    ")"
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "emergency_access_sessions_v2",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("super_admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_type", sa.Text(), nullable=False),
        sa.Column("scope_patient_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_ip", postgresql.INET(), nullable=False),
        sa.Column("created_user_agent", sa.Text(), nullable=False),
        sa.Column("decrypt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("export_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("export_payload_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(SESSION_SCOPE_CHECK, name="ck_emergency_access_sessions_v2_scope"),
        sa.CheckConstraint(
            "expires_at <= requested_at + interval '60 minutes'",
            name="ck_emergency_access_sessions_v2_duration",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["super_admin_id"], ["users.id"], ondelete="RESTRICT"),
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

    op.create_index(
        "idx_emergency_sessions_v2_tenant",
        "emergency_access_sessions_v2",
        ["tenant_id"],
    )
    op.create_index(
        "idx_emergency_sessions_v2_admin",
        "emergency_access_sessions_v2",
        ["super_admin_id"],
    )
    op.create_index(
        "idx_emergency_sessions_v2_active",
        "emergency_access_sessions_v2",
        ["tenant_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "idx_emergency_sessions_v2_expiry",
        "emergency_access_sessions_v2",
        ["expires_at"],
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
    op.execute(
        """
        CREATE TRIGGER trg_prevent_identity_update_v2
        BEFORE UPDATE ON emergency_access_sessions_v2
        FOR EACH ROW
        EXECUTE FUNCTION prevent_emergency_identity_update_v2();
        """
    )

    op.create_table(
        "emergency_access_events_v2",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("super_admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=True),
        sa.Column("payload_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(EVENT_TYPE_CHECK, name="ck_emergency_access_events_v2_type"),
        sa.ForeignKeyConstraint(["session_id"], ["emergency_access_sessions_v2.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["super_admin_id"], ["users.id"], ondelete="RESTRICT"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_emergency_event_modification_v2()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Emergency audit events are immutable';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_prevent_event_modification_v2
        BEFORE UPDATE OR DELETE ON emergency_access_events_v2
        FOR EACH ROW
        EXECUTE FUNCTION prevent_emergency_event_modification_v2();
        """
    )

    op.create_index(
        "idx_emergency_events_v2_session",
        "emergency_access_events_v2",
        ["session_id"],
    )
    op.create_index(
        "idx_emergency_events_v2_tenant",
        "emergency_access_events_v2",
        ["tenant_id"],
    )
    op.create_index(
        "idx_emergency_events_v2_type",
        "emergency_access_events_v2",
        ["event_type"],
    )
    op.execute(
        "CREATE INDEX idx_emergency_events_v2_created_desc ON emergency_access_events_v2 (created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_emergency_events_v2_created_desc")
    op.drop_index("idx_emergency_events_v2_type", table_name="emergency_access_events_v2")
    op.drop_index("idx_emergency_events_v2_tenant", table_name="emergency_access_events_v2")
    op.drop_index("idx_emergency_events_v2_session", table_name="emergency_access_events_v2")
    op.execute("DROP TRIGGER IF EXISTS trg_prevent_event_modification_v2 ON emergency_access_events_v2")
    op.execute("DROP FUNCTION IF EXISTS prevent_emergency_event_modification_v2")
    op.drop_table("emergency_access_events_v2")

    op.execute("DROP TRIGGER IF EXISTS trg_prevent_identity_update_v2 ON emergency_access_sessions_v2")
    op.execute("DROP FUNCTION IF EXISTS prevent_emergency_identity_update_v2")
    op.drop_index("idx_emergency_sessions_v2_expiry", table_name="emergency_access_sessions_v2")
    op.drop_index("idx_emergency_sessions_v2_active", table_name="emergency_access_sessions_v2")
    op.drop_index("idx_emergency_sessions_v2_admin", table_name="emergency_access_sessions_v2")
    op.drop_index("idx_emergency_sessions_v2_tenant", table_name="emergency_access_sessions_v2")
    op.execute("ALTER TABLE emergency_access_sessions_v2 DROP CONSTRAINT IF EXISTS emergency_no_overlap_v2")
    op.drop_table("emergency_access_sessions_v2")
