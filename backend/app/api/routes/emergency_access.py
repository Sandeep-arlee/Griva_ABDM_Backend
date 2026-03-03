from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.core.config import settings
from app.routing.policy import RouteClass, route_policy
from app.schemas.emergency_access import EmergencyAccessRequest, EmergencyAccessResponse
from app.services.emergency_access_service import (
    EmergencyAccessError,
    request_emergency_access,
    revoke_emergency_access,
)
from app.security.metrics import security_metrics
from app.security.security_log import log_emergency_event

router = APIRouter(prefix="/admin/emergency-access", tags=["emergency-access"])


def _session_response(session) -> EmergencyAccessResponse:
    return EmergencyAccessResponse(
        id=str(session.id),
        tenant_id=str(session.tenant_id),
        super_admin_id=str(session.super_admin_id),
        reason=session.reason,
        approved_by=str(session.approved_by) if session.approved_by else None,
        approved_at=session.approved_at,
        created_at=session.created_at,
        expires_at=session.expires_at,
        revoked_at=session.revoked_at,
    )


@router.post(
    "/request",
    response_model=EmergencyAccessResponse,
    status_code=status.HTTP_201_CREATED,
)
@route_policy(
    route_class=RouteClass.TENANT_WRITE,
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
def request_access(
    payload: EmergencyAccessRequest,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_roles("SUPERADMIN", require_emergency_session=False)),
) -> EmergencyAccessResponse:
    if not settings.emergency_access_enabled:
        raise HTTPException(status_code=403, detail="EMERGENCY_ACCESS_DISABLED")
    tenant_id = db.info.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="TENANT_REQUIRED")

    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    try:
        session = request_emergency_access(
            db,
            user,
            tenant_id,
            payload.reason,
            payload.duration_minutes,
            ip,
            user_agent,
        )
        db.commit()
        log_emergency_event(
            event_type="REQUESTED",
            tenant_id=str(session.tenant_id),
            super_admin_id=str(session.super_admin_id),
            session_id=str(session.id),
            ip=ip,
        )
        log_emergency_event(
            event_type="APPROVED",
            tenant_id=str(session.tenant_id),
            super_admin_id=str(session.super_admin_id),
            session_id=str(session.id),
            ip=ip,
        )
        security_metrics.inc("emergency_sessions_created_total")
    except EmergencyAccessError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=500, detail="EMERGENCY_ACCESS_REQUEST_FAILED") from exc

    return _session_response(session)


@router.post("/revoke/{session_id}", response_model=EmergencyAccessResponse)
@route_policy(
    route_class=RouteClass.TENANT_WRITE,
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
def revoke_access(
    session_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_roles("SUPERADMIN", require_emergency_session=False)),
) -> EmergencyAccessResponse:
    if not settings.emergency_access_enabled:
        raise HTTPException(status_code=403, detail="EMERGENCY_ACCESS_DISABLED")
    tenant_id = db.info.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="TENANT_REQUIRED")

    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    try:
        session = revoke_emergency_access(
            db,
            user,
            tenant_id,
            session_id,
            ip,
            user_agent,
        )
        db.commit()
        log_emergency_event(
            event_type="REVOKED",
            tenant_id=str(session.tenant_id),
            super_admin_id=str(session.super_admin_id),
            session_id=str(session.id),
            ip=ip,
        )
    except EmergencyAccessError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=500, detail="EMERGENCY_ACCESS_REVOKE_FAILED") from exc

    return _session_response(session)
