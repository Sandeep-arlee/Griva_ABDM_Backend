from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from app.api.deps import get_db, require_roles
from app.models.emergency_access_v2 import EmergencyAccessSessionV2
from app.routing.policy import RouteClass, route_policy
from app.schemas.emergency_access import (
    EmergencyActiveSessionResponse,
    EmergencyAlertItem,
    EmergencyAlertsResponse,
    EmergencyAuditEventResponse,
    EmergencyAuditPageResponse,
)

router = APIRouter(prefix="/governance/emergency", tags=["governance"])


@router.get("/active", response_model=list[EmergencyActiveSessionResponse])
@route_policy(
    route_class=RouteClass.TENANT_READ,
    tenant_scoped=True,
    phi_access=False,
    decrypts_data=False,
    consent_required=False,
    export_endpoint=False,
    governance_mutation=False,
    abdm_signed_route=False,
    patient_scope_supported=False,
    patient_id_source=None,
    background_capable=False,
    response_static=True,
    allowed_during_emergency=True,
)
def list_active_emergency_sessions(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("SUPERADMIN", require_emergency_session=False)),
) -> list[EmergencyActiveSessionResponse]:
    tenant_id = db.info.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TENANT_REQUIRED")

    sessions = (
        db.query(EmergencyAccessSessionV2)
        .filter(
            EmergencyAccessSessionV2.tenant_id == tenant_id,
            EmergencyAccessSessionV2.revoked_at.is_(None),
            EmergencyAccessSessionV2.expires_at > func.now(),
        )
        .order_by(EmergencyAccessSessionV2.approved_at.desc())
        .all()
    )

    return [
        EmergencyActiveSessionResponse(
            session_id=str(session.id),
            approved_at=session.approved_at,
            expires_at=session.expires_at,
            decrypt_count=session.decrypt_count,
            export_count=session.export_count,
            export_payload_bytes=session.export_payload_bytes,
        )
        for session in sessions
    ]


@router.get("/audit", response_model=EmergencyAuditPageResponse)
@route_policy(
    route_class=RouteClass.TENANT_READ,
    tenant_scoped=True,
    phi_access=False,
    decrypts_data=False,
    consent_required=False,
    export_endpoint=False,
    governance_mutation=False,
    abdm_signed_route=False,
    patient_scope_supported=False,
    patient_id_source=None,
    background_capable=False,
    response_static=True,
    allowed_during_emergency=True,
)
def list_emergency_audit_events(
    limit: int | None = None,
    cursor: str | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("SUPERADMIN", require_emergency_session=False)),
) -> EmergencyAuditPageResponse:
    tenant_id = db.info.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TENANT_REQUIRED")

    limit_val = 50 if limit is None else limit
    if limit_val < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="INVALID_LIMIT")
    if limit_val > 100:
        limit_val = 100

    cursor_created_at = None
    cursor_id = None
    if cursor:
        cursor_created_at, cursor_id = _decode_cursor(cursor)

    if cursor_created_at is None:
        rows = db.execute(
            text(
                """
                SELECT
                    id,
                    session_id,
                    event_type,
                    created_at,
                    record_count,
                    payload_size_bytes
                FROM emergency_access_events_v2
                WHERE tenant_id = :tenant_id
                ORDER BY created_at DESC, id DESC
                LIMIT :limit
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "limit": limit_val,
            },
        ).fetchall()
    else:
        rows = db.execute(
            text(
                """
                SELECT
                    id,
                    session_id,
                    event_type,
                    created_at,
                    record_count,
                    payload_size_bytes
                FROM emergency_access_events_v2
                WHERE tenant_id = :tenant_id
                  AND (created_at, id) < (:cursor_created_at, :cursor_id)
                ORDER BY created_at DESC, id DESC
                LIMIT :limit
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "cursor_created_at": cursor_created_at,
                "cursor_id": cursor_id,
                "limit": limit_val,
            },
        ).fetchall()

    items: list[EmergencyAuditEventResponse] = []
    for row in rows:
        event_type = row.event_type
        decrypt_delta = 1 if event_type == "DECRYPT" else 0
        export_delta = row.record_count if event_type == "EXPORT" and row.record_count else 0
        export_bytes_delta = (
            row.payload_size_bytes if event_type == "EXPORT" and row.payload_size_bytes else 0
        )
        items.append(
            EmergencyAuditEventResponse(
                event_id=str(row.id),
                session_id=str(row.session_id),
                event_type=event_type,
                created_at=row.created_at,
                decrypt_count_delta=decrypt_delta,
                export_count_delta=export_delta,
                export_payload_bytes_delta=export_bytes_delta,
            )
        )

    next_cursor = None
    if rows and len(rows) == limit_val:
        last = rows[-1]
        next_cursor = _encode_cursor(last.created_at, last.id)

    return EmergencyAuditPageResponse(items=items, next_cursor=next_cursor)


@router.get("/alerts", response_model=EmergencyAlertsResponse)
@route_policy(
    route_class=RouteClass.TENANT_READ,
    tenant_scoped=True,
    phi_access=False,
    decrypts_data=False,
    consent_required=False,
    export_endpoint=False,
    governance_mutation=False,
    abdm_signed_route=False,
    patient_scope_supported=False,
    patient_id_source=None,
    background_capable=False,
    response_static=True,
    allowed_during_emergency=True,
)
def list_emergency_alerts(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("SUPERADMIN", require_emergency_session=False)),
) -> EmergencyAlertsResponse:
    tenant_id = db.info.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TENANT_REQUIRED")

    row = db.execute(
        text(
            """
            SELECT
                COALESCE(SUM(CASE WHEN event_type = 'EXPORT' THEN record_count ELSE 0 END), 0) AS export_total,
                COALESCE(SUM(CASE WHEN event_type = 'EXPORT' THEN payload_size_bytes ELSE 0 END), 0) AS export_bytes_total,
                COALESCE(SUM(CASE WHEN event_type = 'APPROVED' THEN 1 ELSE 0 END), 0) AS approvals_total,
                COALESCE(SUM(CASE WHEN event_type = 'DECRYPT' THEN 1 ELSE 0 END), 0) AS decrypt_total,
                now() AS evaluated_at
            FROM emergency_access_events_v2
            WHERE tenant_id = :tenant_id
              AND created_at > now() - interval '60 minutes'
            """
        ),
        {"tenant_id": str(tenant_id)},
    ).fetchone()

    decrypt_total = int(row.decrypt_total or 0)
    export_total = int(row.export_total or 0)
    export_bytes_total = int(row.export_bytes_total or 0)
    approvals_total = int(row.approvals_total or 0)
    evaluated_at = row.evaluated_at

    alerts: list[EmergencyAlertItem] = []

    if decrypt_total >= 50:
        alerts.append(
            EmergencyAlertItem(
                type="HIGH_DECRYPT_VOLUME",
                value=decrypt_total,
                threshold=50,
            )
        )
    if export_total >= 10:
        alerts.append(
            EmergencyAlertItem(
                type="HIGH_EXPORT_VOLUME",
                value=export_total,
                threshold=10,
            )
        )
    if export_bytes_total >= 25_000_000:
        alerts.append(
            EmergencyAlertItem(
                type="LARGE_EXPORT_VOLUME",
                value=export_bytes_total,
                threshold=25_000_000,
            )
        )
    if approvals_total >= 5:
        alerts.append(
            EmergencyAlertItem(
                type="FREQUENT_EMERGENCY_APPROVALS",
                value=approvals_total,
                threshold=5,
            )
        )

    return EmergencyAlertsResponse(alerts=alerts, evaluated_at=evaluated_at)


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
        payload = json.loads(raw.decode("utf-8"))
        created_at_raw = payload.get("created_at")
        cursor_id_raw = payload.get("id")
        if not created_at_raw or not cursor_id_raw:
            raise ValueError("missing")
        created_at = datetime.fromisoformat(created_at_raw)
        cursor_id = uuid.UUID(str(cursor_id_raw))
        return created_at, cursor_id
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="INVALID_CURSOR") from exc


def _encode_cursor(created_at: datetime, cursor_id) -> str:
    payload = {"created_at": created_at.isoformat(), "id": str(cursor_id)}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
