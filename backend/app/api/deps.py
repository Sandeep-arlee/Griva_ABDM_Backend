from datetime import datetime, timedelta, timezone
import uuid
from fastapi import Request
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.signature import (
    canonicalize_request,
    hash_body,
    load_public_key,
    utc_now_iso,
    verify_signature,
)
from fastapi.routing import APIRoute
from starlette.routing import Match

from app.routing.policy import POLICY_REGISTRY
from app.security.token_decoder import decode_token
from app.security.user_context import AuthenticatedUser, PreTenantUser, build_authenticated_user
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.internal_consent import InternalConsent
from app.models.tenant import Tenant
from app.models.trusted_request import TrustedRequest
from app.services.idempotency_service import check_request
from app.tenancy import get_current_tenant_id


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_db(request: Request):
    db = getattr(request.state, "db", None)
    if db is not None:
        yield db
        return
    db = SessionLocal()
    tenant_id = get_current_tenant_id()
    if settings.strict_tenant_mode and not tenant_id:
        db.close()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TENANT_REQUIRED")
    if tenant_id:
        exists = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not exists:
            db.close()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TENANT_NOT_FOUND")
        db.info["tenant_id"] = tenant_id
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> AuthenticatedUser | PreTenantUser:
    payload = decode_token(token)
    token_type = payload.get("type")

    policy = _resolve_policy(request)
    allow_pre_tenant = bool(policy and getattr(policy, "allow_pre_tenant", False))

    if token_type == "pre_tenant":
        if not allow_pre_tenant:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="PRE_TENANT_NOT_ALLOWED")
        subject = payload.get("sub") or payload.get("user_id")
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token subject",
            )
        return PreTenantUser(id=str(subject))

    if token_type == "refresh":
        if request.url.path not in {"/api/auth/refresh", "/api/auth/hpr/refresh"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="REFRESH_NOT_ALLOWED")
        if not payload.get("user_id") or not payload.get("tenant_id") or not payload.get("membership_id"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token structure")
        user_ctx = build_authenticated_user(db, payload, require_membership=True)
        if user_ctx is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
        return user_ctx

    if token_type != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    if (
        not payload.get("user_id")
        or not payload.get("tenant_id")
        or not payload.get("membership_id")
        or not payload.get("role")
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token structure")

    user_ctx = build_authenticated_user(db, payload, require_role=True, require_membership=True)
    if user_ctx is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")

    if policy and policy.tenant_scoped:
        header_tenant = getattr(request.state, "tenant_id", None)
        if not header_tenant:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TENANT_REQUIRED")
        if not user_ctx.tenant_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="TENANT_MISMATCH")
        if str(header_tenant) != str(user_ctx.tenant_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="TENANT_MISMATCH")

    return user_ctx


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


def require_roles(*roles: str, require_emergency_session: bool = True):
    def _enforce(
        request: Request,
        user: AuthenticatedUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> AuthenticatedUser:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return _enforce


def assert_internal_consent(db: Session, patient_id: str, purpose: str) -> InternalConsent:
    tenant_id = db.info.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TENANT_REQUIRED")

    consent = (
        db.query(InternalConsent)
        .filter(
            InternalConsent.tenant_id == tenant_id,
            InternalConsent.subject_patient_id == patient_id,
            InternalConsent.purpose == purpose,
            InternalConsent.status == "GRANTED",
        )
        .first()
    )
    if not consent:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="INTERNAL_CONSENT_REQUIRED")
    return consent


def _audit_signature_event(
    db: Session,
    request_id: str | None,
    key_id: str | None,
    outcome: str,
    path: str,
    status_code: int,
    timestamp: str | None,
) -> None:
    effective_request_id = request_id or f"missing-{uuid.uuid4()}"
    meta = {
        "key_id": key_id,
        "outcome": outcome,
        "path": path,
        "timestamp": timestamp or utc_now_iso(),
    }
    tenant_id = db.info.get("tenant_id")
    audit = AuditLog(
        tenant_id=tenant_id,
        actor="system",
        action="ABDM_SIGNATURE",
        resource_type="request",
        resource_id=effective_request_id,
        event_type="ABDM_SIGNATURE",
        request_id=effective_request_id,
        hip_id=None,
        hiu_id=None,
        cm_id=None,
        consent_id=None,
        status_code=status_code,
        meta=meta,
    )
    try:
        db.add(audit)
        db.flush()
    except IntegrityError:
        db.rollback()


def verify_abdm_signature(request: Request, db: Session = Depends(get_db)) -> None:
    signature = request.headers.get("X-Signature")
    key_id = request.headers.get("X-Key-Id")
    request_id = request.headers.get("X-Request-ID")
    timestamp = request.headers.get("X-Timestamp")

    if not signature or not key_id or not request_id or not timestamp:
        _audit_signature_event(
            db,
            request_id,
            key_id,
            "MISSING_SIGNATURE",
            request.url.path,
            status.HTTP_401_UNAUTHORIZED,
            timestamp,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MISSING_SIGNATURE")

    try:
        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        _audit_signature_event(
            db,
            request_id,
            key_id,
            "TIMESTAMP_OUT_OF_RANGE",
            request.url.path,
            status.HTTP_401_UNAUTHORIZED,
            timestamp,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="TIMESTAMP_OUT_OF_RANGE") from exc

    now = datetime.now(timezone.utc)
    if abs(now - ts) > timedelta(seconds=settings.abdm_timestamp_tolerance_seconds):
        _audit_signature_event(
            db,
            request_id,
            key_id,
            "TIMESTAMP_OUT_OF_RANGE",
            request.url.path,
            status.HTTP_401_UNAUTHORIZED,
            timestamp,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="TIMESTAMP_OUT_OF_RANGE")

    public_key = load_public_key(key_id, db=db)
    if not public_key:
        _audit_signature_event(
            db,
            request_id,
            key_id,
            "INVALID_SIGNATURE",
            request.url.path,
            status.HTTP_401_UNAUTHORIZED,
            timestamp,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_SIGNATURE")

    body = request.state.raw_body or b""
    body_hash = hash_body(body)
    canonical = canonicalize_request(
        request.method,
        request.url.path,
        request_id,
        timestamp,
        body_hash,
    )

    if not verify_signature(signature, public_key, canonical):
        _audit_signature_event(
            db,
            request_id,
            key_id,
            "INVALID_SIGNATURE",
            request.url.path,
            status.HTTP_401_UNAUTHORIZED,
            timestamp,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_SIGNATURE")

    db.add(TrustedRequest(request_id=request_id, signature=signature))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        tenant_id = db.info.get("tenant_id")
        if tenant_id and check_request(db, tenant_id, request_id, request.url.path):
            _audit_signature_event(
                db,
                request_id,
                key_id,
                "REPLAY_DETECTED",
                request.url.path,
                status.HTTP_200_OK,
                timestamp,
            )
            return
        _audit_signature_event(
            db,
            request_id,
            key_id,
            "REPLAY_DETECTED",
            request.url.path,
            status.HTTP_409_CONFLICT,
            timestamp,
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="REPLAY_DETECTED")

    _audit_signature_event(
        db,
        request_id,
        key_id,
        "SIGNATURE_OK",
        request.url.path,
        status.HTTP_200_OK,
        timestamp,
    )
