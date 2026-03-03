from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import assert_internal_consent, get_db, require_roles
from app.models.medical_record import MedicalRecord
from app.routing.policy import PatientIdSource, RouteClass, route_policy
from app.schemas.records import RecordResponse

router = APIRouter(prefix="/api/patients", tags=["patients"])


@router.get("/{patient_id}/records", response_model=list[RecordResponse])
@route_policy(
    route_class=RouteClass.TENANT_READ,
    tenant_scoped=True,
    phi_access=True,
    decrypts_data=False,
    consent_required=True,
    export_endpoint=False,
    governance_mutation=False,
    abdm_signed_route=False,
    patient_scope_supported=True,
    patient_id_source=PatientIdSource.PATH,
    background_capable=False,
    response_static=True,
    allowed_during_emergency=True,
)
def list_records(
    patient_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("ADMIN", "DOCTOR", "SUPERADMIN")),
) -> list[RecordResponse]:
    assert_internal_consent(db, patient_id=patient_id, purpose="CARE")
    records = (
        db.query(MedicalRecord)
        .filter(MedicalRecord.patient_id == patient_id)
        .order_by(MedicalRecord.created_at.desc())
        .all()
    )
    return [
        RecordResponse(
            id=str(record.id),
            patient_id=record.patient_id,
            record_type=record.record_type,
            uri=record.uri,
            created_at=record.created_at,
        )
        for record in records
    ]
