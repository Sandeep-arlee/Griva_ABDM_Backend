from __future__ import annotations

from typing import Optional

import ipaddress

from fastapi import HTTPException, Request, status
from fastapi.routing import APIRoute
from starlette.responses import JSONResponse
from starlette.routing import Match
from sqlalchemy import and_, func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.models.emergency_access_v2 import (
    EmergencyAccessEventV2,
    EmergencyAccessSessionV2,
    EmergencyEventType,
)
from app.security.token_decoder import decode_token
from app.security.user_context import AuthenticatedUser, build_authenticated_user
from app.routing.policy import POLICY_REGISTRY
from app.security.security_log import log_emergency_event


class EmergencyEnforcementMiddleware(BaseHTTPMiddleware):
    """
    Phase E emergency access enforcement.

    Assumes (by upstream contract):
        - tenant_id is injected into request.state.tenant_id
        - db session is injected into request.state.db
        - user is injected into request.state.user
        - route policy is injected into request.state.route_policy
    """

    async def dispatch(self, request: Request, call_next):
        try:
            db: Session | None = getattr(request.state, "db", None)
            user = getattr(request.state, "user", None)
            tenant_id = getattr(request.state, "tenant_id", None)
            route = request.scope.get("route")
            if not isinstance(route, APIRoute):
                route = self._resolve_route(request)
                if route is None:
                    return await call_next(request)
            policy = POLICY_REGISTRY.get(route.name)

            if db is None or policy is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="EMERGENCY_ENFORCEMENT_MISCONFIGURED",
                )

            if user is None:
                user = self._load_user_from_token(request, db)
                request.state.user = user

            if not self._emergency_required(user, policy):
                return await call_next(request)

            if not settings.emergency_access_enabled:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="EMERGENCY_ACCESS_DISABLED",
                )

            if tenant_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TENANT_REQUIRED")

            session = self._get_active_session(
                db=db,
                tenant_id=tenant_id,
                super_admin_id=user.id,
            )
            if session is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="EMERGENCY_ACCESS_REQUIRED",
                )

            self._insert_used_event(db=db, request=request, session=session)
            self._touch_last_used(db=db, session_id=session.id)

            request.state.emergency_session = session
            return await call_next(request)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @staticmethod
    def _emergency_required(user, policy) -> bool:
        if user is None:
            return False
        return (
            policy.tenant_scoped
            and policy.phi_access
            and user.role == "SUPERADMIN"
            and not policy.abdm_signed_route
        )

    @staticmethod
    def _get_active_session(
        db: Session,
        tenant_id,
        super_admin_id,
    ) -> Optional[EmergencyAccessSessionV2]:
        stmt = (
            select(EmergencyAccessSessionV2)
            .where(
                and_(
                    EmergencyAccessSessionV2.tenant_id == tenant_id,
                    EmergencyAccessSessionV2.super_admin_id == super_admin_id,
                    EmergencyAccessSessionV2.revoked_at.is_(None),
                    EmergencyAccessSessionV2.approved_at <= func.now(),
                    EmergencyAccessSessionV2.expires_at > func.now(),
                )
            )
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def _resolve_route(request: Request) -> APIRoute | None:
        for route in request.app.router.routes:
            if not isinstance(route, APIRoute):
                continue
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                return route
        return None

    @staticmethod
    def _load_user_from_token(request: Request, db: Session) -> AuthenticatedUser | None:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return None
        token = auth_header.split(" ", 1)[1].strip()
        try:
            payload = decode_token(token)
        except Exception:  # noqa: BLE001
            return None
        if payload.get("type") != "access":
            return None
        if (
            not payload.get("user_id")
            or not payload.get("tenant_id")
            or not payload.get("membership_id")
            or not payload.get("role")
        ):
            return None
        user_ctx = build_authenticated_user(
            db,
            payload,
            require_role=True,
            require_membership=True,
        )
        return user_ctx

    @staticmethod
    def _insert_used_event(
        db: Session,
        request: Request,
        session: EmergencyAccessSessionV2,
    ) -> None:
        ip = _safe_ip(request)
        event = EmergencyAccessEventV2(
            session_id=session.id,
            tenant_id=session.tenant_id,
            super_admin_id=session.super_admin_id,
            event_type=EmergencyEventType.USED,
            resource_type=None,
            resource_id=None,
            record_count=None,
            payload_size_bytes=None,
            ip=ip,
            user_agent=request.headers.get("user-agent", "unknown"),
            created_at=func.now(),
        )
        db.add(event)
        try:
            db.flush()
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="EMERGENCY_AUDIT_FAILED",
            ) from exc
        log_emergency_event(
            event_type="USED",
            tenant_id=str(session.tenant_id),
            super_admin_id=str(session.super_admin_id),
            session_id=str(session.id),
            ip=ip,
        )

    @staticmethod
    def _touch_last_used(db: Session, session_id) -> None:
        try:
            db.execute(
                update(EmergencyAccessSessionV2)
                .where(EmergencyAccessSessionV2.id == session_id)
                .values(last_used_at=func.now())
            )
            db.flush()
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="EMERGENCY_AUDIT_FAILED",
            ) from exc


def _safe_ip(request: Request) -> str:
    raw = request.client.host if request.client else None
    if not raw:
        return "0.0.0.0"
    try:
        ipaddress.ip_address(raw)
        return raw
    except ValueError:
        return "0.0.0.0"
