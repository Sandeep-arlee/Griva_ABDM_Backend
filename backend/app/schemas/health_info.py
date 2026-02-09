from datetime import datetime
from pydantic import BaseModel, Field


class HIRequestDateRange(BaseModel):
    from_: datetime = Field(alias="from")
    to: datetime


class HIRequest(BaseModel):
    requestId: str
    timestamp: datetime
    hiTypes: list[str]
    dateRange: HIRequestDateRange


class HealthInformationRequest(BaseModel):
    transactionId: str
    consentId: str
    hiRequest: HIRequest


class HIEntry(BaseModel):
    content: str
    media: str


class HealthInformationResponse(BaseModel):
    transactionId: str
    entries: list[HIEntry]


class HealthInformationRequestAccepted(BaseModel):
    status: str = "ACCEPTED"
    requestId: str
