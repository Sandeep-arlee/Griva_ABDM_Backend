import uuid
from sqlalchemy import DateTime, ForeignKey, String, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Index

from app.db.base import Base


class PatientAbhaLink(Base):
    __tablename__ = "patient_abha_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    abha_address_enc: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    abha_number_enc: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    abha_hash: Mapped[str] = mapped_column(String, nullable=False)
    link_status: Mapped[str] = mapped_column(String, nullable=False, default="VERIFIED")
    verified_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_abha_links_tenant_hash", "tenant_id", "abha_hash", unique=True),
    )
