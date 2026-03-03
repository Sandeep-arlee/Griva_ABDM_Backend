"""add emergency access exclusion constraint

Revision ID: c1d2e3f4a5b6
Revises: b7d6c1a2e8f9
Create Date: 2026-02-20 00:00:00.000000
"""
from alembic import op

revision = "c1d2e3f4a5b6"
down_revision = "b7d6c1a2e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        ALTER TABLE emergency_access_sessions
        ADD CONSTRAINT emergency_no_overlap
        EXCLUDE USING gist (
            tenant_id WITH =,
            super_admin_id WITH =,
            tstzrange(created_at, expires_at) WITH &&
        )
        WHERE (revoked_at IS NULL)
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE emergency_access_sessions DROP CONSTRAINT IF EXISTS emergency_no_overlap")
