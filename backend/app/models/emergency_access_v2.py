from __future__ import annotations

import datetime
import enum
import uuid
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Enum as SAEnum

from app.db.base import Base


class EmergencyScopeType(str, enum.Enum):
    TENANT_WIDE = "TENANT_WIDE"
    PATIENT_SCOPED = "PATIENT_SCOPED"


class EmergencyEventType(str, enum.Enum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    USED = "USED"
    EXPORT = "EXPORT"
    DECRYPT = "DECRYPT"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class EmergencyAccessSessionV2(Base):
    __tablename__ = "emergency_access_sessions_v2"
    __table_args__ = (
        CheckConstraint(
            "expires_at > approved_at",
            name="ck_emergency_access_sessions_v2_time_order",
        ),
        CheckConstraint(
            "expires_at <= approved_at + interval '60 minutes'",
            name="ck_emergency_access_sessions_v2_duration",
        ),
        CheckConstraint(
            "(scope_type = 'TENANT_WIDE' AND scope_patient_id IS NULL) "
            "OR (scope_type = 'PATIENT_SCOPED' AND scope_patient_id IS NOT NULL)",
            name="ck_emergency_access_sessions_v2_scope",
        ),
        Index(
            "idx_emergency_sessions_v2_tenant",
            "tenant_id",
        ),
        Index(
            "idx_emergency_sessions_v2_admin",
            "super_admin_id",
        ),
        Index(
            "idx_emergency_sessions_v2_active",
            "tenant_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index(
            "idx_emergency_sessions_v2_expiry",
            "expires_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Emergency session identifier.",
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Tenant scope for this emergency session.",
        info={"immutable": True},
    )
    super_admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="SUPER_ADMIN user authorized for the session.",
        info={"immutable": True},
    )
    scope_type: Mapped[EmergencyScopeType] = mapped_column(
        SAEnum(
            EmergencyScopeType,
            name="emergency_scope_type_v2",
            native_enum=False,
            create_constraint=False,
        ),
        nullable=False,
        comment="Emergency scope classification.",
        info={"immutable": True},
    )
    scope_patient_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Patient scope when scope_type is PATIENT_SCOPED.",
        info={"immutable": True},
    )
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Justification for emergency access.",
    )
    requested_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Request timestamp (DB time expected).",
        info={"immutable": True},
    )
    approved_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Approval timestamp (DB time).",
        info={"immutable": True},
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Expiration timestamp (DB time).",
        info={"immutable": True},
    )
    revoked_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Revocation timestamp, if revoked.",
    )
    created_ip: Mapped[str] = mapped_column(
        INET,
        nullable=False,
        comment="Requester IP address.",
    )
    created_user_agent: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Requester user agent.",
    )
    decrypt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Count of decrypt operations in this session.",
    )
    export_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Cumulative count of exported records in this session.",
    )
    export_payload_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Cumulative exported payload size in bytes.",
    )
    last_used_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last time this session was used.",
    )

    tenant = relationship(
        "Tenant",
        lazy="select",
        viewonly=True,
        cascade="none",
    )
    super_admin = relationship(
        "User",
        lazy="select",
        viewonly=True,
        cascade="none",
    )
    events = relationship(
        "EmergencyAccessEventV2",
        lazy="select",
        viewonly=True,
        cascade="none",
    )


class EmergencyAccessEventV2(Base):
    __tablename__ = "emergency_access_events_v2"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'REQUESTED','APPROVED','USED','EXPORT','DECRYPT','REVOKED','EXPIRED'"
            ")",
            name="ck_emergency_access_events_v2_type",
        ),
        Index(
            "idx_emergency_events_v2_session",
            "session_id",
        ),
        Index(
            "idx_emergency_events_v2_tenant",
            "tenant_id",
        ),
        Index(
            "idx_emergency_events_v2_type",
            "event_type",
        ),
        Index(
            "idx_emergency_events_v2_created_desc",
            text("created_at DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Emergency audit event identifier.",
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("emergency_access_sessions_v2.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Associated emergency session identifier.",
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Tenant associated with the event.",
    )
    super_admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        comment="SUPER_ADMIN who performed the action.",
    )
    event_type: Mapped[EmergencyEventType] = mapped_column(
        SAEnum(
            EmergencyEventType,
            name="emergency_event_type_v2",
            native_enum=False,
            create_constraint=False,
        ),
        nullable=False,
        comment="Emergency event classification.",
    )
    resource_type: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Resource type associated with the event.",
    )
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Resource identifier associated with the event.",
    )
    record_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of records accessed or exported.",
    )
    payload_size_bytes: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Payload size in bytes for export events.",
    )
    ip: Mapped[str] = mapped_column(
        INET,
        nullable=False,
        comment="Requester IP address.",
    )
    user_agent: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Requester user agent.",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Event creation timestamp (DB time).",
    )

    session = relationship(
        "EmergencyAccessSessionV2",
        lazy="select",
        viewonly=True,
        cascade="none",
    )
