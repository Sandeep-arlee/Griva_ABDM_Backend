"""add_users_identity_check_constraint

Revision ID: c578654dbb81
Revises: 1ceb217264bc
Create Date: 2026-03-03 15:08:11.565744

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c578654dbb81'
down_revision: Union[str, None] = '1ceb217264bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_users_identity_present",
        "users",
        "email IS NOT NULL OR hpr_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_identity_present", "users", type_="check")
