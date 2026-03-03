from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.audit_log import AuditLog
from app.models.consent_grant import ConsentGrant
from app.models.consent_revocation import ConsentRevocation
from app.models.internal_consent import InternalConsent
from app.routing.policy import RouteClass, route_policy
from app.schemas.internal_consent import (
    InternalConsentGrantRequest,
    InternalConsentRevokeRequest,
    InternalConsentResponse,
)

router = APIRouter(prefix="/api/internal-consents", tags=["internal-consents"])


@router.post("/grant", response_model=InternalConsentResponse, status_code=status.HTTP_201_CREATED)
@route_policy(
    route_class=RouteClass.GOVERNANCE_MUTATION,
    tenant_scoped=True,
    phi_access=False,
    decrypts_data=False,
    consent_required=False,
    export_endpoint=False,
    governance_mutation=True,
    abdm_signed_route=False,
    patient_scope_supported=False,
    patient_id_source=None,
    background_capable=False,
    response_static=True,
    allowed_during_emergency=False,
)
def grant_internal_consent(
    payload: InternalConsentGrantRequest,
    db: Session = Depends(get_db),
    user=Depends(require_roles("ADMIN", "DOCTOR", "SUPERADMIN")),
) -> InternalConsentResponse:
    tenant_id = db.info.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="TENANT_REQUIRED")

    consent = (
        db.query(InternalConsent)
        .filter(
            InternalConsent.tenant_id == tenant_id,
            InternalConsent.subject_patient_id == payload.patient_id,
            InternalConsent.purpose == payload.purpose,
        )
        .first()
    )
    if not consent:
        consent = InternalConsent(
            tenant_id=tenant_id,
            subject_patient_id=payload.patient_id,
            purpose=payload.purpose,
            status="GRANTED",
            meta=payload.metadata or {},
        )
        db.add(consent)
        try:
            db.flush()
        except Exception:  # noqa: BLE001
            db.rollback()
            consent = (
                db.query(InternalConsent)
                .filter(
                    InternalConsent.tenant_id == tenant_id,
                    InternalConsent.subject_patient_id == payload.patient_id,
                    InternalConsent.purpose == payload.purpose,
                )
                .first()
            )
            if not consent:
                raise HTTPException(status_code=409, detail="INTERNAL_CONSENT_CONFLICT")
    else:
        consent.status = "GRANTED"

    db.add(
        ConsentGrant(
            tenant_id=tenant_id,
            internal_consent_id=consent.id,
            granted_by_user_id=user.id,
            scope=payload.scope or {},
        )
    )

    db.add(
        AuditLog(
            event_type="INTERNAL_CONSENT_GRANT",
            request_id=None,
            hip_id=None,
            hiu_id=None,
            cm_id=None,
            consent_id=str(consent.id),
            status_code=201,
            meta={"patient_id": payload.patient_id, "purpose": payload.purpose},
            tenant_id=tenant_id,
        )
    )

    db.commit()
    return InternalConsentResponse(
        id=str(consent.id),
        patient_id=consent.subject_patient_id,
        purpose=consent.purpose,
        status=consent.status,
        created_at=consent.created_at,
    )


@router.post("/revoke", response_model=InternalConsentResponse)
@route_policy(
    route_class=RouteClass.GOVERNANCE_MUTATION,
    tenant_scoped=True,
    phi_access=False,
    decrypts_data=False,
    consent_required=False,
    export_endpoint=False,
    governance_mutation=True,
    abdm_signed_route=False,
    patient_scope_supported=False,
    patient_id_source=None,
    background_capable=False,
    response_static=True,
    allowed_during_emergency=False,
)
def revoke_internal_consent(
    payload: InternalConsentRevokeRequest,
    db: Session = Depends(get_db),
    user=Depends(require_roles("ADMIN", "DOCTOR", "SUPERADMIN")),
) -> InternalConsentResponse:
    tenant_id = db.info.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="TENANT_REQUIRED")

    consent = (
        db.query(InternalConsent)
        .filter(
            InternalConsent.tenant_id == tenant_id,
            InternalConsent.subject_patient_id == payload.patient_id,
            InternalConsent.purpose == payload.purpose,
        )
        .first()
    )
    if not consent:
        raise HTTPException(status_code=404, detail="INTERNAL_CONSENT_NOT_FOUND")

    consent.status = "REVOKED"
    db.add(
        ConsentRevocation(
            tenant_id=tenant_id,
            internal_consent_id=consent.id,
            revoked_by_user_id=user.id,
            reason=payload.reason,
            meta=payload.meta or {},
        )
    )
    db.add(
        AuditLog(
            event_type="INTERNAL_CONSENT_REVOKE",
            request_id=None,
            hip_id=None,
            hiu_id=None,
            cm_id=None,
            consent_id=str(consent.id),
            status_code=200,
            meta={"patient_id": payload.patient_id, "purpose": payload.purpose, "reason": payload.reason},
            tenant_id=tenant_id,
        )
    )
    db.commit()
    return InternalConsentResponse(
        id=str(consent.id),
        patient_id=consent.subject_patient_id,
        purpose=consent.purpose,
        status=consent.status,
        created_at=consent.created_at,
    )
