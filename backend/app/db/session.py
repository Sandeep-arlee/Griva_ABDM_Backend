from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, with_loader_criteria

from app.core.config import settings
from app.db.base import Base
from app.models.user import User
from app.models.user_tenant_membership import UserTenantMembership

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_TENANT_EXCLUSIONS = {User}


@event.listens_for(Session, "do_orm_execute")
def _add_tenant_criteria(execute_state):
    tenant_id = execute_state.session.info.get("tenant_id")
    if not tenant_id:
        return
    statement = execute_state.statement
    if not getattr(statement, "is_select", False):
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            UserTenantMembership,
            lambda model_cls, tenant_id=tenant_id: model_cls.tenant_id == tenant_id,
            include_aliases=True,
        )
    )
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        if cls in _TENANT_EXCLUSIONS:
            continue
        if not hasattr(cls, "tenant_id"):
            continue
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(cls, lambda model_cls, tenant_id=tenant_id: model_cls.tenant_id == tenant_id, include_aliases=True)
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
