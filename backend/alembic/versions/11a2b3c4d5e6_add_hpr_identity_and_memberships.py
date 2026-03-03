"""add hpr identity and memberships

Revision ID: 11a2b3c4d5e6
Revises: 10f8257c2287
Create Date: 2026-02-26 14:12:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "11a2b3c4d5e6"
down_revision: Union[str, None] = "10f8257c2287"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("hpr_id", sa.String(), nullable=True))
    op.add_column("users", sa.Column("hpr_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("hpr_profile_enc", postgresql.JSONB(), nullable=True))
    op.add_column("users", sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"))
    op.create_unique_constraint("uq_users_hpr_id", "users", ["hpr_id"])
    op.create_check_constraint(
        "ck_users_status",
        "users",
        "status IN ('ACTIVE','DISABLED')",
    )

    op.create_table(
        "user_tenant_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_user_tenant"),
    )
    op.create_check_constraint(
        "ck_user_tenant_membership_status",
        "user_tenant_memberships",
        "status IN ('ACTIVE','INVITED','SUSPENDED')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_tenant_membership_status", "user_tenant_memberships", type_="check")
    op.drop_table("user_tenant_memberships")

    op.drop_constraint("ck_users_status", "users", type_="check")
    op.drop_constraint("uq_users_hpr_id", "users", type_="unique")
    op.drop_column("users", "status")
    op.drop_column("users", "hpr_profile_enc")
    op.drop_column("users", "hpr_verified_at")
    op.drop_column("users", "hpr_id")
