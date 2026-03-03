from contextvars import ContextVar
from typing import Optional
from uuid import UUID

_tenant_id_ctx: ContextVar[Optional[UUID]] = ContextVar("tenant_id", default=None)


def set_current_tenant_id(tenant_id: Optional[UUID]):
    return _tenant_id_ctx.set(tenant_id)


def reset_current_tenant_id(token) -> None:
    _tenant_id_ctx.reset(token)


def get_current_tenant_id() -> Optional[UUID]:
    return _tenant_id_ctx.get()
