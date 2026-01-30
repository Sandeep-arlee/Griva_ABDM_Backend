import uuid
from sqlalchemy import String, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String, nullable=True)
    hip_id: Mapped[str | None] = mapped_column(String, nullable=True)
    hiu_id: Mapped[str | None] = mapped_column(String, nullable=True)
    cm_id: Mapped[str | None] = mapped_column(String, nullable=True)
    consent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    timestamp: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
