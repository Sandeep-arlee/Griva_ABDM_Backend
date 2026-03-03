from __future__ import annotations

from datetime import datetime, timezone
import secrets
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.security import create_access_token, create_pre_tenant_token, create_refresh_token, decode_token
from app.models.tenant import Tenant
from app.models.user import User
from app.models.user_tenant_membership import UserTenantMembership
from app.routing.policy import RouteClass, route_policy
from app.schemas.auth import RefreshRequest
from app.security.user_context import PreTenantUser
from app.services.hpr_oauth import (
    build_auth_url,
    create_oauth_state,
    decode_oauth_state,
    exchange_code_for_token,
    generate_pkce_pair,
    validate_id_token,
)
from app.services.platform_crypto import encrypt_hpr_profile

router = APIRouter(prefix="/api/auth/hpr", tags=["auth"])


@router.get("/start")
@route_policy(
    route_class=RouteClass.SYSTEM,
    tenant_scoped=False,
    phi_access=False,
    decrypts_data=False,
    consent_required=False,
    export_endpoint=False,
    governance_mutation=False,
    abdm_signed_route=False,
    patient_scope_supported=False,
    patient_id_source=None,
    background_capable=False,
    response_static=True,
    allowed_during_emergency=True,
)
def start_oauth(response: Response):
    state = secrets.token_urlsafe(16)
    nonce = secrets.token_urlsafe(16)
    verifier, challenge = generate_pkce_pair()
    state_token = create_oauth_state(state, nonce, verifier)

    response.set_cookie(
        key=settings.hpr_oauth_state_cookie_name,
        value=state_token,
        httponly=True,
        secure=settings.hpr_oauth_cookie_secure,
        samesite="lax",
        max_age=settings.hpr_oauth_state_ttl_seconds,
        path="/api/auth/hpr/callback",
    )

    return {"redirect_url": build_auth_url(state, nonce, challenge)}


@router.get("/callback")
@route_policy(
    route_class=RouteClass.SYSTEM,
    tenant_scoped=False,
    phi_access=False,
    decrypts_data=False,
    consent_required=False,
    export_endpoint=False,
    governance_mutation=False,
    abdm_signed_route=False,
    patient_scope_supported=False,
    patient_id_source=None,
    background_capable=False,
    response_static=True,
    allowed_during_emergency=True,
)
def hpr_callback(
    request: Request,
    response: Response,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    state_token = request.cookies.get(settings.hpr_oauth_state_cookie_name)
    if not state_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_STATE")

    try:
        stored = decode_oauth_state(state_token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_STATE") from exc

    if stored.get("state") != state:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_STATE")

    token_response = exchange_code_for_token(code, stored["verifier"])
    id_token = token_response.get("id_token")
    if not id_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MISSING_ID_TOKEN")

    payload = validate_id_token(id_token)
    if payload.get("nonce") != stored.get("nonce"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_NONCE")

    hpr_id = payload.get("sub")
    if not hpr_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_HPR_ID")

    profile = {
        "name": payload.get("name"),
        "registration_number": payload.get("registration_number"),
        "specialty": payload.get("specialty"),
        "email": payload.get("email"),
    }

    user = db.query(User).filter(User.hpr_id == hpr_id).first()
    if not user:
        user = User(
            email=None,
            hashed_password=None,
            role=None,
            tenant_id=None,
            hpr_id=hpr_id,
            status="ACTIVE",
            hpr_verified_at=datetime.now(timezone.utc),
            hpr_profile_enc=encrypt_hpr_profile(profile),
        )
        db.add(user)
        db.flush()
    elif user.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="USER_DISABLED")

    pre_token = create_pre_tenant_token(str(user.id))
    response.delete_cookie(settings.hpr_oauth_state_cookie_name, path="/api/auth/hpr/callback")
    return {"pre_tenant_token": pre_token, "expires_in": settings.pre_tenant_token_expire_seconds}


@router.get("/memberships")
@route_policy(
    route_class=RouteClass.SYSTEM,
    tenant_scoped=False,
    phi_access=False,
    decrypts_data=False,
    consent_required=False,
    export_endpoint=False,
    governance_mutation=False,
    abdm_signed_route=False,
    patient_scope_supported=False,
    patient_id_source=None,
    background_capable=False,
    response_static=True,
    allowed_during_emergency=True,
    allow_pre_tenant=True,
)
def list_memberships(
    user: PreTenantUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        user_id = uuid.UUID(user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user id") from exc
    memberships = (
        db.query(UserTenantMembership, Tenant)
        .join(Tenant, Tenant.id == UserTenantMembership.tenant_id)
        .filter(UserTenantMembership.user_id == user_id)
        .all()
    )
    return {
        "memberships": [
            {
                "membership_id": str(membership.id),
                "tenant_id": str(membership.tenant_id),
                "tenant_name": tenant.name,
                "role": membership.role,
                "status": membership.status,
            }
            for membership, tenant in memberships
        ]
    }


@router.post("/select-tenant")
@route_policy(
    route_class=RouteClass.SYSTEM,
    tenant_scoped=False,
    phi_access=False,
    decrypts_data=False,
    consent_required=False,
    export_endpoint=False,
    governance_mutation=False,
    abdm_signed_route=False,
    patient_scope_supported=False,
    patient_id_source=None,
    background_capable=False,
    response_static=True,
    allowed_during_emergency=True,
    allow_pre_tenant=True,
)
def select_tenant(
    tenant_id: str = Body(..., embed=True),
    user: PreTenantUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        user_id = uuid.UUID(user.id)
        tenant_uuid = uuid.UUID(str(tenant_id))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant id") from exc
    membership = (
        db.query(UserTenantMembership)
        .filter(
            UserTenantMembership.user_id == user_id,
            UserTenantMembership.tenant_id == tenant_uuid,
            UserTenantMembership.status == "ACTIVE",
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="INVALID_MEMBERSHIP")

    claims = {
        "user_id": str(user_id),
        "tenant_id": str(membership.tenant_id),
        "membership_id": str(membership.id),
        "role": membership.role,
    }
    access = create_access_token(str(user_id), extra_claims=claims)
    refresh = create_refresh_token(str(user_id), extra_claims=claims)
    return {"access_token": access, "refresh_token": refresh, "expires_in": settings.access_token_expire_minutes * 60}


@router.post("/refresh")
@route_policy(
    route_class=RouteClass.SYSTEM,
    tenant_scoped=False,
    phi_access=False,
    decrypts_data=False,
    consent_required=False,
    export_endpoint=False,
    governance_mutation=False,
    abdm_signed_route=False,
    patient_scope_supported=False,
    patient_id_source=None,
    background_capable=False,
    response_static=True,
    allowed_during_emergency=True,
)
def refresh_tokens(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        token_payload = decode_token(payload.refresh_token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    if token_payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    if (
        not token_payload.get("user_id")
        or not token_payload.get("tenant_id")
        or not token_payload.get("membership_id")
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token structure")

    try:
        user_id = uuid.UUID(str(token_payload["user_id"]))
        membership_id = uuid.UUID(str(token_payload["membership_id"]))
        tenant_uuid = uuid.UUID(str(token_payload["tenant_id"]))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token structure") from exc

    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="USER_DISABLED")

    membership = (
        db.query(UserTenantMembership)
        .filter(
            UserTenantMembership.id == membership_id,
            UserTenantMembership.user_id == user_id,
            UserTenantMembership.tenant_id == tenant_uuid,
            UserTenantMembership.status == "ACTIVE",
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="INVALID_MEMBERSHIP")

    claims = {
        "user_id": str(user_id),
        "tenant_id": str(tenant_uuid),
        "membership_id": str(membership.id),
        "role": membership.role,
    }
    access = create_access_token(str(user_id), extra_claims=claims)
    refresh = create_refresh_token(str(user_id), extra_claims=claims)
    return {"access_token": access, "refresh_token": refresh, "expires_in": settings.access_token_expire_minutes * 60}
