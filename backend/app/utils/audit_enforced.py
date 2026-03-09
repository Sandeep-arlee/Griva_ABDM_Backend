from __future__ import annotations

from functools import wraps
import inspect
import uuid
from typing import Any, Callable, Optional

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def _find_db(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Session | None:
    db = kwargs.get("db")
    if isinstance(db, Session):
        return db
    for arg in args:
        if isinstance(arg, Session):
            return arg
    return None


def _find_request(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Request | None:
    req = kwargs.get("request")
    if isinstance(req, Request):
        return req
    for arg in args:
        if isinstance(arg, Request):
            return arg
    return None


def _find_response(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Response | None:
    resp = kwargs.get("response")
    if isinstance(resp, Response):
        return resp
    for arg in args:
        if isinstance(arg, Response):
            return arg
    return None


def _find_user(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
    for key in ("user", "_user", "current_user"):
        if key in kwargs:
            return kwargs[key]
    for arg in args:
        if hasattr(arg, "role") and hasattr(arg, "id"):
            return arg
    return None


def audited(
    action: str,
    *,
    resource_type: str | None = None,
    resource_id_getter: Callable[[Any, tuple[Any, ...], dict[str, Any]], Optional[str]] | None = None,
    status_code_getter: Callable[[Any, tuple[Any, ...], dict[str, Any]], Optional[int]] | None = None,
    should_audit: Callable[[Any, tuple[Any, ...], dict[str, Any]], bool] | None = None,
    use_request_id: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        is_async = inspect.iscoroutinefunction(func)

        def _apply_audit(result: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
            db = _find_db(args, kwargs)
            if db is None:
                return
            if should_audit is not None:
                try:
                    if not should_audit(result, args, kwargs):
                        return
                except Exception:  # noqa: BLE001
                    return

            request = _find_request(args, kwargs)
            response = _find_response(args, kwargs)
            user = _find_user(args, kwargs)

            request_id = None
            if request is not None:
                request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")

            resource_id = None
            if resource_id_getter:
                try:
                    resource_id = resource_id_getter(result, args, kwargs)
                except Exception:  # noqa: BLE001
                    resource_id = None

            tenant_id = db.info.get("tenant_id")
            for pending in db.new:
                if not isinstance(pending, AuditLog):
                    continue
                if pending.action != action:
                    continue
                if tenant_id and pending.tenant_id != tenant_id:
                    continue
                if resource_id and pending.resource_id == resource_id:
                    return
                if use_request_id and request_id and pending.request_id == request_id:
                    return

            query = db.query(AuditLog).filter(AuditLog.action == action)
            if tenant_id:
                query = query.filter(AuditLog.tenant_id == tenant_id)
            if use_request_id and request_id:
                query = query.filter(AuditLog.request_id == request_id)
            elif resource_id:
                query = query.filter(AuditLog.resource_id == resource_id)

            if query.first():
                return

            actor = "system"
            if user is not None and hasattr(user, "id"):
                actor = str(user.id)

            resource_type_value = resource_type or func.__name__
            resource_id_value = resource_id or request_id or f"unknown-{uuid.uuid4()}"

            status_code = 200
            if status_code_getter:
                try:
                    value = status_code_getter(result, args, kwargs)
                    if value is not None:
                        status_code = int(value)
                except Exception:  # noqa: BLE001
                    status_code = status_code
            elif response is not None and getattr(response, "status_code", None):
                status_code = int(response.status_code)

            audit = AuditLog(
                tenant_id=tenant_id,
                actor=actor,
                action=action,
                resource_type=resource_type_value,
                resource_id=resource_id_value,
                event_type=action,
                request_id=request_id or f"auto-{uuid.uuid4()}",
                hip_id=None,
                hiu_id=None,
                cm_id=None,
                consent_id=None,
                status_code=status_code,
                meta={},
            )
            was_in_tx = db.in_transaction()
            try:
                db.add(audit)
                db.flush()
                if not was_in_tx:
                    db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()

        if is_async:
            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                result = await func(*args, **kwargs)
                _apply_audit(result, args, kwargs)
                return result

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            return_value = result
            _apply_audit(return_value, args, kwargs)
            return return_value

        return sync_wrapper

    return decorator
