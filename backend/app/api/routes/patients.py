from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.medical_record import MedicalRecord
from app.schemas.records import RecordResponse

router = APIRouter(prefix="/api/patients", tags=["patients"])


@router.get("/{patient_id}/records", response_model=list[RecordResponse])
def list_records(
    patient_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_roles("ADMIN", "DOCTOR", "SUPERADMIN")),
) -> list[RecordResponse]:
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
