from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, with_loader_criteria

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.consent import Consent
from app.models.consent_event import ConsentEvent
from app.models.health_information_event import HealthInformationEvent
from app.models.health_information_request import HealthInformationRequest
from app.models.internal_consent import InternalConsent
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.models.tenant_key import TenantKey
from app.models.trusted_request import TrustedRequest
from app.models.user_tenant_membership import UserTenantMembership
from app.models.consent_grant import ConsentGrant
from app.models.consent_revocation import ConsentRevocation
from app.models.emergency_access_session import EmergencyAccessSession

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_TENANT_MODELS = (
    Patient,
    Consent,
    ConsentEvent,
    MedicalRecord,
    AuditLog,
    HealthInformationRequest,
    HealthInformationEvent,
    TrustedRequest,
    TenantKey,
    InternalConsent,
    ConsentGrant,
    ConsentRevocation,
    EmergencyAccessSession,
    UserTenantMembership,
)


@event.listens_for(Session, "do_orm_execute")
def _add_tenant_criteria(execute_state):
    tenant_id = execute_state.session.info.get("tenant_id")
    if not tenant_id or not execute_state.is_select:
        return
    for model in _TENANT_MODELS:
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(model, lambda cls, tenant_id=tenant_id: cls.tenant_id == tenant_id, include_aliases=True)
        )


@event.listens_for(Session, "before_flush")
def _set_tenant_id(session, flush_context, instances):
    tenant_id = session.info.get("tenant_id")
    if not tenant_id:
        return
    for obj in session.new:
        if obj.__class__.__name__ in {"TrustedKey", "User"}:
            continue
        if hasattr(obj, "tenant_id") and getattr(obj, "tenant_id") is None:
            setattr(obj, "tenant_id", tenant_id)
