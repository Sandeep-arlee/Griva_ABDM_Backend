import uuid
import enum
from sqlalchemy import String, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.consent import Consent
from app.models.tenant_scoped import TenantScoped


class HealthInformationRequestStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


hi_request_status_enum = Enum(
    HealthInformationRequestStatus,
    name="hi_request_status",
    create_type=False,
)


class HealthInformationRequest(TenantScoped, Base):
    __tablename__ = "health_information_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    consent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("consents.id"), nullable=False)
    hip_id: Mapped[str] = mapped_column(String, nullable=False)
    hiu_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[HealthInformationRequestStatus] = mapped_column(hi_request_status_enum, nullable=False)
    date_range: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    consent: Mapped[Consent] = relationship()
    events: Mapped[list["HealthInformationEvent"]] = relationship(back_populates="health_information_request")
