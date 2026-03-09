from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import ipaddress
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.emergency_access_v2 import (
    EmergencyAccessEventV2,
    EmergencyAccessSessionV2,
    EmergencyEventType,
    EmergencyScopeType,
)
from app.models.user import User


@dataclass(frozen=True)
class EmergencyAccessSessionInfo:
    id: UUID
    tenant_id: UUID
    super_admin_id: UUID
    reason: str
    approved_by: UUID | None
    approved_at: datetime | None
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class EmergencyAccessError(Exception):
    def __init__(self, detail: str, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _to_info(session: EmergencyAccessSessionV2) -> EmergencyAccessSessionInfo:
    return EmergencyAccessSessionInfo(
        id=session.id,
        tenant_id=session.tenant_id,
        super_admin_id=session.super_admin_id,
        reason=session.reason,
        approved_by=None,
        approved_at=session.approved_at,
        created_at=session.requested_at,
        expires_at=session.expires_at,
        revoked_at=session.revoked_at,
    )


def _audit_emergency_event(
    db: Session,
    event_type: str,
    tenant_id: UUID,
    super_admin_id: UUID,
    session_id: UUID,
    reason: str,
    ip: str | None,
    user_agent: str | None,
) -> None:
    audit = AuditLog(
        actor=str(super_admin_id),
        action=event_type,
        resource_type="emergency_session",
        resource_id=str(session_id),
        event_type=event_type,
        request_id=f"emergency-{session_id}",
        hip_id=None,
        hiu_id=None,
        cm_id=None,
        consent_id=None,
        status_code=200,
        meta={
            "super_admin_id": str(super_admin_id),
            "tenant_id": str(tenant_id),
            "session_id": str(session_id),
            "reason": reason,
            "ip": ip,
            "user_agent": user_agent,
        },
        tenant_id=tenant_id,
    )
    db.add(audit)


def _insert_emergency_event_v2(
    db: Session,
    session: EmergencyAccessSessionV2,
    event_type: EmergencyEventType,
    ip: str | None,
    user_agent: str | None,
) -> None:
    normalized_ip = _normalize_ip(ip)
    db.add(
        EmergencyAccessEventV2(
            session_id=session.id,
            tenant_id=session.tenant_id,
            super_admin_id=session.super_admin_id,
            event_type=event_type,
            resource_type=None,
            resource_id=None,
            record_count=None,
            payload_size_bytes=None,
            ip=normalized_ip,
            user_agent=user_agent or "unknown",
            created_at=func.now(),
        )
    )


def _normalize_ip(ip: str | None) -> str:
    if not ip:
        return "127.0.0.1"
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return "127.0.0.1"


def request_emergency_access(
    db: Session,
    user: User,
    tenant_id: UUID,
    reason: str,
    duration_minutes: int | None,
    ip: str | None,
    user_agent: str | None,
) -> EmergencyAccessSessionInfo:
    if user.role != "SUPERADMIN":
        raise EmergencyAccessError("FORBIDDEN", 403)

    trimmed_reason = (reason or "").strip()
    if len(trimmed_reason) < settings.emergency_access_min_reason_length:
        raise EmergencyAccessError("REASON_TOO_SHORT", 400)

    duration = settings.emergency_access_max_minutes if duration_minutes is None else duration_minutes
    if duration <= 0 or duration > settings.emergency_access_max_minutes:
        raise EmergencyAccessError("INVALID_DURATION", 400)

    now = datetime.now(timezone.utc)
    # Fail-closed: do not allow overlapping active sessions for the same tenant/admin.
    active = (
        db.query(EmergencyAccessSessionV2)
        .filter(
            EmergencyAccessSessionV2.tenant_id == tenant_id,
            EmergencyAccessSessionV2.super_admin_id == user.id,
            EmergencyAccessSessionV2.revoked_at.is_(None),
            EmergencyAccessSessionV2.expires_at > now,
        )
        .first()
    )
    if active:
        raise EmergencyAccessError("EMERGENCY_ACCESS_ACTIVE", 409)

    normalized_ip = _normalize_ip(ip)
    expires_at = now + timedelta(minutes=duration)
    session = EmergencyAccessSessionV2(
        tenant_id=tenant_id,
        super_admin_id=user.id,
        scope_type=EmergencyScopeType.TENANT_WIDE,
        scope_patient_id=None,
        reason=trimmed_reason,
        requested_at=now,
        approved_at=now,
        expires_at=expires_at,
        created_ip=normalized_ip,
        created_user_agent=user_agent or "unknown",
        decrypt_count=0,
        export_count=0,
        export_payload_bytes=0,
        last_used_at=None,
    )
    db.add(session)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise EmergencyAccessError("EMERGENCY_ACCESS_ACTIVE", 409) from exc

    _insert_emergency_event_v2(db, session, EmergencyEventType.REQUESTED, normalized_ip, user_agent)
    _insert_emergency_event_v2(db, session, EmergencyEventType.APPROVED, normalized_ip, user_agent)

    _audit_emergency_event(
        db,
        "EMERGENCY_ACCESS_REQUESTED",
        tenant_id,
        user.id,
        session.id,
        trimmed_reason,
        normalized_ip,
        user_agent,
    )
    _audit_emergency_event(
        db,
        "EMERGENCY_ACCESS_GRANTED",
        tenant_id,
        user.id,
        session.id,
        trimmed_reason,
        normalized_ip,
        user_agent,
    )

    return _to_info(session)


def validate_emergency_access(
    db: Session,
    tenant_id: UUID,
    super_admin_id: UUID,
) -> EmergencyAccessSessionInfo | None:
    now = datetime.now(timezone.utc)
    session = (
        db.query(EmergencyAccessSessionV2)
        .filter(
            EmergencyAccessSessionV2.tenant_id == tenant_id,
            EmergencyAccessSessionV2.super_admin_id == super_admin_id,
            EmergencyAccessSessionV2.revoked_at.is_(None),
            EmergencyAccessSessionV2.expires_at > now,
        )
        .order_by(EmergencyAccessSessionV2.expires_at.desc())
        .first()
    )
    if not session:
        return None
    return _to_info(session)


def log_emergency_access_used(
    db: Session,
    session: EmergencyAccessSessionInfo,
    ip: str | None,
    user_agent: str | None,
) -> None:
    _audit_emergency_event(
        db,
        "EMERGENCY_ACCESS_USED",
        session.tenant_id,
        session.super_admin_id,
        session.id,
        session.reason,
        ip,
        user_agent,
    )
    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise EmergencyAccessError("EMERGENCY_ACCESS_AUDIT_FAILED", 500) from exc


def revoke_emergency_access(
    db: Session,
    user: User,
    tenant_id: UUID,
    session_id: UUID,
    ip: str | None,
    user_agent: str | None,
) -> EmergencyAccessSessionInfo:
    if user.role != "SUPERADMIN":
        raise EmergencyAccessError("FORBIDDEN", 403)

    session = (
        db.query(EmergencyAccessSessionV2)
        .filter(
            EmergencyAccessSessionV2.id == session_id,
            EmergencyAccessSessionV2.tenant_id == tenant_id,
            EmergencyAccessSessionV2.super_admin_id == user.id,
        )
        .first()
    )
    if not session:
        raise EmergencyAccessError("EMERGENCY_ACCESS_NOT_FOUND", 404)
    if session.revoked_at is not None:
        raise EmergencyAccessError("EMERGENCY_ACCESS_ALREADY_REVOKED", 409)

    now = datetime.now(timezone.utc)
    session.revoked_at = now
    db.add(session)

    normalized_ip = _normalize_ip(ip)
    _insert_emergency_event_v2(db, session, EmergencyEventType.REVOKED, normalized_ip, user_agent)
    _audit_emergency_event(
        db,
        "EMERGENCY_ACCESS_REVOKED",
        tenant_id,
        user.id,
        session.id,
        session.reason,
        normalized_ip,
        user_agent,
    )

    return _to_info(session)
