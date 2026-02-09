"""add health information request/event tables

Revision ID: 4b1c8a9b7f1b
Revises: 2a532a436406
Create Date: 2026-02-04 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "4b1c8a9b7f1b"
down_revision = "2a532a436406"
branch_labels = None
depends_on = None

hi_request_status = sa.Enum(
    "REQUESTED",
    "PROCESSING",
    "COMPLETED",
    "FAILED",
    name="hi_request_status",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "health_information_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("consent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hip_id", sa.String(), nullable=False),
        sa.Column("hiu_id", sa.String(), nullable=False),
        sa.Column("status", hi_request_status, nullable=False),
        sa.Column("date_range", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["consent_id"], ["consents.id"]),
    )
    op.create_index(
        "ix_health_information_requests_request_id",
        "health_information_requests",
        ["request_id"],
        unique=True,
    )

    op.create_table(
        "health_information_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "health_information_request_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("event_payload", postgresql.JSONB(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["health_information_request_id"],
            ["health_information_requests.id"],
        ),
    )


def downgrade() -> None:
    op.drop_table("health_information_events")
    op.drop_index("ix_health_information_requests_request_id", table_name="health_information_requests")
    op.drop_table("health_information_requests")
    hi_request_status.drop(op.get_bind(), checkfirst=True)
