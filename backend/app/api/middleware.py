from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request
from starlette.routing import Match
from fastapi.routing import APIRoute

from app.core.config import settings
from app.security.token_decoder import decode_token
from app.security.user_context import build_authenticated_user
from app.db.session import SessionLocal
from app.models.tenant import Tenant
from app.routing.policy import POLICY_REGISTRY
from app.tenancy import reset_current_tenant_id, set_current_tenant_id
from app.tenancy import get_current_tenant_id


class RawBodyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        body = await request.body()
        request.state.raw_body = body
        return await call_next(request)


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        policy = _resolve_policy(request)
        if policy and not policy.tenant_scoped:
            tenant_id = None
            token = set_current_tenant_id(tenant_id)
            request.state.tenant_id = tenant_id
            try:
                return await call_next(request)
            finally:
                reset_current_tenant_id(token)

        if settings.strict_tenant_mode and request.url.path not in {"/", "/docs", "/openapi.json", "/redoc"}:
            if "X-Tenant-ID" not in request.headers:
                return JSONResponse(status_code=400, content={"detail": "TENANT_REQUIRED"})

        tenant_header = request.headers.get("X-Tenant-ID")
        tenant_id = None
        if tenant_header:
            try:
                tenant_id = UUID(tenant_header)
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "INVALID_TENANT_ID"})

        token = set_current_tenant_id(tenant_id)
        request.state.tenant_id = tenant_id
        try:
            return await call_next(request)
        finally:
            reset_current_tenant_id(token)


class DBSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        policy = _resolve_policy(request)
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id is None:
            tenant_id = get_current_tenant_id()

        if policy and policy.tenant_scoped and not tenant_id:
            return JSONResponse(status_code=400, content={"detail": "TENANT_REQUIRED"})

        db = SessionLocal()
        if "tenant_id" in db.info:
            db.close()
            raise RuntimeError("Tenant already bound to DB session")

        if policy and not policy.tenant_scoped:
            request.state.db = db
            try:
                response = await call_next(request)
                db.commit()
                return response
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

        if settings.strict_tenant_mode and not tenant_id and request.url.path not in {
            "/",
            "/docs",
            "/openapi.json",
            "/redoc",
        }:
            db.close()
            return JSONResponse(status_code=400, content={"detail": "TENANT_REQUIRED"})
        if tenant_id:
            exists = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not exists:
                db.close()
                return JSONResponse(status_code=400, content={"detail": "TENANT_NOT_FOUND"})
            db.info["tenant_id"] = tenant_id
        request.state.db = db
        try:
            response = await call_next(request)
            db.commit()
            return response
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


class AuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.user = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            try:
                payload = decode_token(token)
                if payload.get("type") == "access":
                    db = getattr(request.state, "db", None)
                    if db is not None:
                        if (
                            payload.get("user_id")
                            and payload.get("tenant_id")
                            and payload.get("membership_id")
                            and payload.get("role")
                        ):
                            user_ctx = build_authenticated_user(
                                db,
                                payload,
                                require_role=True,
                                require_membership=True,
                            )
                        else:
                            user_ctx = None
                        if user_ctx is not None:
                            header_tenant = getattr(request.state, "tenant_id", None)
                            if header_tenant and user_ctx.tenant_id:
                                if str(header_tenant) != str(user_ctx.tenant_id):
                                    request.state.user = None
                                else:
                                    request.state.user = user_ctx
                            else:
                                request.state.user = user_ctx
            except Exception:  # noqa: BLE001
                request.state.user = None
        return await call_next(request)


def _resolve_policy(request: Request):
    route = request.scope.get("route")
    if not isinstance(route, APIRoute):
        for candidate in request.app.router.routes:
            if not isinstance(candidate, APIRoute):
                continue
            match, _ = candidate.matches(request.scope)
            if match == Match.FULL:
                route = candidate
                break
        else:
            return None
    return POLICY_REGISTRY.get(route.name)
