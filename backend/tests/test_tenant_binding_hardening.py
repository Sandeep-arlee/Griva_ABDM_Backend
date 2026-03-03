import anyio
import pytest
from uuid import uuid4

from starlette.requests import Request
from starlette.responses import Response

from app.api.middleware import DBSessionMiddleware
from app.db.session import SessionLocal
from app.main import app
from app.models.tenant import Tenant
from app.routing.policy import POLICY_REGISTRY, validate_route_policies


def _ensure_policy_registry() -> None:
    if not POLICY_REGISTRY:
        validate_route_policies(app)


def _make_request(path: str, tenant_id):
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "app": app,
    }
    request = Request(scope)
    request.state.tenant_id = tenant_id
    return request


def test_db_session_tenant_binding_immutable():
    _ensure_policy_registry()
    tenant_id = uuid4()
    with SessionLocal() as db:
        db.add(Tenant(id=tenant_id, name=f"Tenant {uuid4().hex[:6]}"))
        db.commit()

    request = _make_request(f"/api/patients/{uuid4().hex}/records", tenant_id)
    middleware = DBSessionMiddleware(app)
    captured: dict[str, object] = {}

    async def call_next(req: Request):
        db = req.state.db
        captured["before"] = db.info.get("tenant_id")
        req.state.tenant_id = uuid4()
        captured["after"] = db.info.get("tenant_id")
        return Response("ok")

    anyio.run(lambda: middleware.dispatch(request, call_next))

    assert captured["before"] == tenant_id
    assert captured["after"] == tenant_id


def test_db_session_double_bind_guard(monkeypatch):
    _ensure_policy_registry()
    tenant_id = uuid4()
    with SessionLocal() as db:
        db.add(Tenant(id=tenant_id, name=f"Tenant {uuid4().hex[:6]}"))
        db.commit()

    rogue_session = SessionLocal()
    rogue_session.info["tenant_id"] = tenant_id

    def _fake_sessionlocal():
        return rogue_session

    monkeypatch.setattr("app.api.middleware.SessionLocal", _fake_sessionlocal)

    request = _make_request(f"/api/patients/{uuid4().hex}/records", tenant_id)
    middleware = DBSessionMiddleware(app)

    async def call_next(req: Request):
        return Response("ok")

    with pytest.raises(RuntimeError, match="Tenant already bound to DB session"):
        anyio.run(lambda: middleware.dispatch(request, call_next))
