"""allow_hpr_users_without_email_password

Revision ID: 1ceb217264bc
Revises: 4e137715189a
Create Date: 2026-03-03 14:46:53.425250

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1ceb217264bc'
down_revision: Union[str, None] = '4e137715189a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "email", nullable=True)
    op.alter_column("users", "hashed_password", nullable=True)
    op.alter_column("users", "role", nullable=True)


def downgrade() -> None:
    op.alter_column("users", "role", nullable=False)
    op.alter_column("users", "hashed_password", nullable=False)
    op.alter_column("users", "email", nullable=False)
