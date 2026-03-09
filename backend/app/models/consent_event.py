import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.consent import Consent, ConsentStatus, consent_status_enum
from app.models.tenant_scoped import TenantScoped


class ConsentEvent(TenantScoped, Base):
    __tablename__ = "consent_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    consent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("consents.id"), nullable=False)
    consent: Mapped[Consent] = relationship(back_populates="events")
    old_status: Mapped[ConsentStatus] = mapped_column(consent_status_enum, nullable=False)
    new_status: Mapped[ConsentStatus] = mapped_column(consent_status_enum, nullable=False)
    event_type: Mapped[ConsentStatus] = mapped_column(consent_status_enum, nullable=False)
    event_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    timestamp: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
