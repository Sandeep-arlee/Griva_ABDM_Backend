from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.security.metrics import security_metrics
from app.security.security_log import log_emergency_event


def enforce_emergency_decrypt(db: Session, session_id: uuid.UUID) -> int:
    """
    Atomically increments decrypt_count for an active emergency session.

    Must be called inside the same transaction as the decrypt operation.
    """
    result = db.execute(
        text(
            """
            UPDATE emergency_access_sessions_v2
            SET decrypt_count = decrypt_count + 1,
                last_used_at = now()
            WHERE id = :session_id
              AND revoked_at IS NULL
              AND approved_at <= now()
              AND expires_at > now()
            RETURNING decrypt_count
            """
        ),
        {"session_id": str(session_id)},
    )

    row = result.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="EMERGENCY_SESSION_INVALID",
        )

    new_count = row[0]
    if new_count > settings.emergency_max_decrypts_per_session:
        db.rollback()
        security_metrics.inc("emergency_cap_exceeded_total")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="EMERGENCY_DECRYPT_CAP_EXCEEDED",
        )

    return new_count


def enforce_emergency_export(
    db: Session,
    *,
    session_id: uuid.UUID,
    record_count: int,
    payload_size_bytes: int,
) -> tuple[int, int]:
    """
    Atomically increments export counters for an active emergency session.

    Must be called inside the same transaction as the export operation.
    """
    if record_count <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="EMERGENCY_EXPORT_INVALID_RECORD_COUNT",
        )
    if payload_size_bytes < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="EMERGENCY_EXPORT_INVALID_PAYLOAD_SIZE",
        )
    result = db.execute(
        text(
            """
            UPDATE emergency_access_sessions_v2
            SET export_count = export_count + :record_count,
                export_payload_bytes = export_payload_bytes + :payload_size_bytes,
                last_used_at = now()
            WHERE id = :session_id
              AND revoked_at IS NULL
              AND approved_at <= now()
              AND expires_at > now()
              AND :record_count <= :max_per_request
              AND export_count + :record_count <= :max_records
              AND export_payload_bytes + :payload_size_bytes <= :max_bytes
            RETURNING export_count, export_payload_bytes
            """
        ),
        {
            "session_id": str(session_id),
            "record_count": record_count,
            "payload_size_bytes": payload_size_bytes,
            "max_per_request": settings.emergency_max_export_records_per_request,
            "max_records": settings.emergency_max_export_records_per_session,
            "max_bytes": settings.emergency_max_export_payload_bytes_per_session,
        },
    )

    row = result.fetchone()
    if row is None:
        active = db.execute(
            text(
                """
                SELECT 1
                FROM emergency_access_sessions_v2
                WHERE id = :session_id
                  AND revoked_at IS NULL
                  AND approved_at <= now()
                  AND expires_at > now()
                """
            ),
            {"session_id": str(session_id)},
        ).fetchone()
        if active is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="EMERGENCY_SESSION_INVALID",
            )
        db.rollback()
        security_metrics.inc("emergency_cap_exceeded_total")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="EMERGENCY_EXPORT_CAP_EXCEEDED",
        )

    return row[0], row[1]


def insert_decrypt_event(
    db: Session,
    *,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    super_admin_id: uuid.UUID,
    ip: str,
    user_agent: str,
) -> None:
    """
    Inserts a DECRYPT audit event for an emergency session.

    Must be executed inside the same transaction as the decrypt operation.
    """
    try:
        db.execute(
            text(
                """
                INSERT INTO emergency_access_events_v2 (
                    id,
                    session_id,
                    tenant_id,
                    super_admin_id,
                    event_type,
                    ip,
                    user_agent,
                    created_at
                )
                VALUES (
                    :id,
                    :session_id,
                    :tenant_id,
                    :super_admin_id,
                    'DECRYPT',
                    :ip,
                    :user_agent,
                    now()
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "session_id": str(session_id),
                "tenant_id": str(tenant_id),
                "super_admin_id": str(super_admin_id),
                "ip": ip,
                "user_agent": user_agent,
            },
        )
        db.flush()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="EMERGENCY_AUDIT_FAILED",
        ) from exc
    log_emergency_event(
        event_type="DECRYPT",
        tenant_id=str(tenant_id),
        super_admin_id=str(super_admin_id),
        session_id=str(session_id),
        ip=ip,
    )
    security_metrics.inc("emergency_decrypt_total")


def insert_export_event(
    db: Session,
    *,
    session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    super_admin_id: uuid.UUID,
    record_count: int,
    payload_size_bytes: int,
    ip: str,
    user_agent: str,
) -> None:
    """
    Inserts an EXPORT audit event for an emergency session.

    Must be executed inside the same transaction as the export operation.
    """
    try:
        db.execute(
            text(
                """
                INSERT INTO emergency_access_events_v2 (
                    id,
                    session_id,
                    tenant_id,
                    super_admin_id,
                    event_type,
                    record_count,
                    payload_size_bytes,
                    ip,
                    user_agent,
                    created_at
                )
                VALUES (
                    :id,
                    :session_id,
                    :tenant_id,
                    :super_admin_id,
                    'EXPORT',
                    :record_count,
                    :payload_size_bytes,
                    :ip,
                    :user_agent,
                    now()
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "session_id": str(session_id),
                "tenant_id": str(tenant_id),
                "super_admin_id": str(super_admin_id),
                "record_count": record_count,
                "payload_size_bytes": payload_size_bytes,
                "ip": ip,
                "user_agent": user_agent,
            },
        )
        db.flush()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="EMERGENCY_AUDIT_FAILED",
        ) from exc
    log_emergency_event(
        event_type="EXPORT",
        tenant_id=str(tenant_id),
        super_admin_id=str(super_admin_id),
        session_id=str(session_id),
        ip=ip,
        extra={
            "record_count": record_count,
            "payload_size_bytes": payload_size_bytes,
        },
    )
    security_metrics.inc("emergency_export_total")
