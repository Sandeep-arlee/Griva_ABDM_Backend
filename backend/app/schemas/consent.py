from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConsentArtefactPatient(BaseModel):
    id: str


class ConsentArtefactEntity(BaseModel):
    id: str


class ConsentPermissionDateRange(BaseModel):
    from_: datetime = Field(alias="from")
    to: datetime


class ConsentPermission(BaseModel):
    accessMode: str
    dateRange: ConsentPermissionDateRange


class ConsentPurpose(BaseModel):
    text: str
    code: str


class ConsentArtefact(BaseModel):
    id: str
    patient: ConsentArtefactPatient
    hiu: ConsentArtefactEntity
    hip: ConsentArtefactEntity
    purpose: ConsentPurpose | None = None
    hiTypes: list[str] | None = None
    permission: ConsentPermission


class ConsentArtefactRef(BaseModel):
    id: str
    artefact: ConsentArtefact | None = None


class ConsentNotification(BaseModel):
    consentRequestId: str
    status: str
    consentArtefacts: list[ConsentArtefactRef]


class ConsentNotifyRequest(BaseModel):
    requestId: str
    timestamp: datetime
    notification: ConsentNotification


class ConsentNotifyResponse(BaseModel):
    status: str = "ACCEPTED"
    received: int


class ConsentErrorResponse(BaseModel):
    error: str
    detail: str | None = None


class ConsentListItem(BaseModel):
    id: str
    abdm_consent_id: str
    patient_id: str
    hiu_id: str
    hip_id: str
    status: str
    valid_from: datetime
    valid_to: datetime
    raw_payload: dict[str, Any]
    created_at: datetime
