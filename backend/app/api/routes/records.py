from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.schemas.records import RecordUploadRequest, RecordResponse

router = APIRouter(prefix="/api/records", tags=["records"])


@router.post("/upload", response_model=RecordResponse)
def upload_record(
    payload: RecordUploadRequest,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("ADMIN", "DOCTOR", "SUPERADMIN")),
) -> RecordResponse:
    record = MedicalRecord(
        patient_id=payload.patient_id,
        record_type=payload.record_type,
        uri=payload.uri,
    )

    patient = db.query(Patient).filter(Patient.patient_id == payload.patient_id).first()
    if patient is None:
        db.add(Patient(patient_id=payload.patient_id))
    db.add(record)
    db.commit()
    db.refresh(record)

    return RecordResponse(
        id=str(record.id),
        patient_id=record.patient_id,
        record_type=record.record_type,
        uri=record.uri,
        created_at=record.created_at,
    )
