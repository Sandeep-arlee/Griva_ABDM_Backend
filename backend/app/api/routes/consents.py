from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.consent import Consent
from app.routing.policy import RouteClass, route_policy
from app.schemas.consent import ConsentListItem

router = APIRouter(prefix="/api/consents", tags=["consents"])


@router.get("", response_model=list[ConsentListItem])
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
def list_consents(
    db: Session = Depends(get_db),
    _user=Depends(require_roles("ADMIN", "DOCTOR", "SUPERADMIN")),
) -> list[ConsentListItem]:
    consents = db.query(Consent).order_by(Consent.created_at.desc()).all()
    return [
        ConsentListItem(
            id=str(consent.id),
            abdm_consent_id=consent.abdm_consent_id,
            patient_id=consent.patient_id,
            hiu_id=consent.hiu_id,
            hip_id=consent.hip_id,
            status=consent.status,
            valid_from=consent.valid_from,
            valid_to=consent.valid_to,
            raw_payload=consent.raw_payload,
            created_at=consent.created_at,
        )
        for consent in consents
    ]
