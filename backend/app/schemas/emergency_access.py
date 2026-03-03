from datetime import datetime
from pydantic import BaseModel


class EmergencyAccessRequest(BaseModel):
    reason: str
    duration_minutes: int | None = None


class EmergencyAccessResponse(BaseModel):
    id: str
    tenant_id: str
    super_admin_id: str
    reason: str
    approved_by: str | None
    approved_at: datetime | None
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class EmergencyActiveSessionResponse(BaseModel):
    session_id: str
    approved_at: datetime
    expires_at: datetime
    decrypt_count: int
    export_count: int
    export_payload_bytes: int


class EmergencyAuditEventResponse(BaseModel):
    event_id: str
    session_id: str
    event_type: str
    created_at: datetime
    decrypt_count_delta: int
    export_count_delta: int
    export_payload_bytes_delta: int


class EmergencyAuditPageResponse(BaseModel):
    items: list[EmergencyAuditEventResponse]
    next_cursor: str | None


class EmergencyAlertItem(BaseModel):
    type: str
    value: int
    threshold: int


class EmergencyAlertsResponse(BaseModel):
    alerts: list[EmergencyAlertItem]
    evaluated_at: datetime
