from datetime import datetime
from typing import Any, Union

from pydantic import BaseModel, Field


class ConsentArtefactPatient(BaseModel):
    id: str


class ConsentArtefactEntity(BaseModel):
    id: str


class ConsentPermissionDateRange(BaseModel):
    from_: datetime = Field(alias="from")
    to: datetime


class ConsentFrequency(BaseModel):
    unit: str
    value: int
    repeats: int


class ConsentPurpose(BaseModel):
    text: str | None = None
    code: str
    refUri: str


class ConsentPermission(BaseModel):
    accessMode: str
    dateRange: ConsentPermissionDateRange
    frequency: ConsentFrequency
    dataEraseAt: datetime


class ConsentArtefact(BaseModel):
    id: str
    patient: ConsentArtefactPatient
    hiu: ConsentArtefactEntity
    hip: ConsentArtefactEntity
    purpose: ConsentPurpose
    hiTypes: list[str]
    permission: ConsentPermission


class ConsentArtefactRef(BaseModel):
    id: str
    artefact: ConsentArtefact


class ConsentNotification(BaseModel):
    consentRequestId: str
    status: str
    consentArtefacts: list[Union[ConsentArtefactRef, ConsentArtefact]]


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
