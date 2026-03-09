from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import assert_internal_consent, get_db, require_roles
from app.models.audit_log import AuditLog
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.routing.policy import PatientIdSource, RouteClass, route_policy
from app.schemas.records import RecordUploadRequest, RecordResponse
from app.utils.audit_enforced import audited

router = APIRouter(prefix="/api/records", tags=["records"])


@audited(
    action="CREATE_MEDICAL_RECORD",
    resource_type="medical_record",
    resource_id_getter=lambda result, _args, _kwargs: str(result.id),
    use_request_id=False,
)
@router.post("/upload", response_model=RecordResponse)
@route_policy(
    route_class=RouteClass.TENANT_WRITE,
    tenant_scoped=True,
    phi_access=True,
    decrypts_data=False,
    consent_required=True,
    export_endpoint=False,
    governance_mutation=False,
    abdm_signed_route=False,
    patient_scope_supported=True,
    patient_id_source=PatientIdSource.BODY,
    background_capable=False,
    response_static=True,
    allowed_during_emergency=True,
)
def upload_record(
    payload: RecordUploadRequest,
    request: Request,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("ADMIN", "DOCTOR", "SUPERADMIN")),
) -> RecordResponse:
    assert_internal_consent(db, patient_id=payload.patient_id, purpose="CARE")
    patient, _created = _ensure_patient(
        db=db,
        patient_id=payload.patient_id,
        user=_user,
    )

    record = MedicalRecord(
        patient_id=payload.patient_id,
        record_type=payload.record_type,
        uri=payload.uri,
    )
    db.add(record)
    db.flush()
    db.add(
        AuditLog(
            actor=str(_user.id),
            action="CREATE_MEDICAL_RECORD",
            resource_type="medical_record",
            resource_id=str(record.id),
            event_type="CREATE_MEDICAL_RECORD",
            request_id=f"record-{record.id}",
            hip_id=None,
            hiu_id=None,
            cm_id=None,
            consent_id=None,
            status_code=201,
            meta={"patient_id": payload.patient_id, "record_type": payload.record_type},
            tenant_id=db.info.get("tenant_id"),
        )
    )
    db.commit()
    db.refresh(record)

    return RecordResponse(
        id=str(record.id),
        patient_id=record.patient_id,
        record_type=record.record_type,
        uri=record.uri,
        created_at=record.created_at,
    )


@audited(
    action="CREATE_PATIENT",
    resource_type="patient",
    resource_id_getter=lambda result, _args, _kwargs: str(result[0].id),
    should_audit=lambda result, _args, _kwargs: bool(result[1]),
    use_request_id=False,
)
def _ensure_patient(
    *,
    db: Session,
    patient_id: str,
    user,
) -> tuple[Patient, bool]:
    patient = db.query(Patient).filter(Patient.patient_id == patient_id).first()
    if patient is None:
        patient = Patient(patient_id=patient_id)
        db.add(patient)
        db.flush()
        db.add(
            AuditLog(
                actor=str(user.id),
                action="CREATE_PATIENT",
                resource_type="patient",
                resource_id=str(patient.id),
                event_type="CREATE_PATIENT",
                request_id=f"patient-{patient.id}",
                hip_id=None,
                hiu_id=None,
                cm_id=None,
                consent_id=None,
                status_code=201,
                meta={"patient_id": patient_id},
                tenant_id=db.info.get("tenant_id"),
            )
        )
        return patient, True
    return patient, False
