from datetime import datetime
from pydantic import BaseModel


class RecordUploadRequest(BaseModel):
    patient_id: str
    record_type: str  
    uri: str


class RecordResponse(BaseModel):
    id: str
    patient_id: str
    record_type: str
    uri: str
    created_at: datetime
