from datetime import datetime
from pydantic import BaseModel


class InternalConsentGrantRequest(BaseModel):
    patient_id: str
    purpose: str
    scope: dict | None = None
    metadata: dict | None = None


class InternalConsentRevokeRequest(BaseModel):
    patient_id: str
    purpose: str
    reason: str
    meta: dict | None = None


class InternalConsentResponse(BaseModel):
    id: str
    patient_id: str
    purpose: str
    status: str
    created_at: datetime
