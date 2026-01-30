import uuid
import enum
from sqlalchemy import String, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

class ConsentStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    GRANTED = "GRANTED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    DENIED = "DENIED"


consent_status_enum = Enum(ConsentStatus, name="consent_status", create_type=False)


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    abdm_consent_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    patient_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    hiu_id: Mapped[str] = mapped_column(String, nullable=False)
    hip_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[ConsentStatus] = mapped_column(consent_status_enum, nullable=False)
    valid_from: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    events: Mapped[list["ConsentEvent"]] = relationship(back_populates="consent")
