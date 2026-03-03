from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.user import User
from app.models.user_tenant_membership import UserTenantMembership
from app.routing.policy import RouteClass, route_policy
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.tenancy import get_current_tenant_id

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
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
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TENANT_REQUIRED")
    membership = (
        db.query(UserTenantMembership)
        .filter(
            UserTenantMembership.user_id == user.id,
            UserTenantMembership.tenant_id == tenant_id,
            UserTenantMembership.status == "ACTIVE",
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="INVALID_MEMBERSHIP")

    claims = {
        "user_id": str(user.id),
        "tenant_id": str(tenant_id),
        "membership_id": str(membership.id),
        "role": membership.role,
    }
    access = create_access_token(user.email, extra_claims=claims)
    refresh = create_refresh_token(user.email, extra_claims=claims)
    return TokenResponse(access_token=access, refresh_token=refresh, role=membership.role)


@router.post("/refresh", response_model=TokenResponse)
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
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        token_payload = decode_token(payload.refresh_token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    if token_payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    email = token_payload.get("sub")
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    if (
        not token_payload.get("user_id")
        or not token_payload.get("tenant_id")
        or not token_payload.get("membership_id")
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token structure")
    membership = (
        db.query(UserTenantMembership)
        .filter(
            UserTenantMembership.id == token_payload["membership_id"],
            UserTenantMembership.user_id == token_payload["user_id"],
            UserTenantMembership.tenant_id == token_payload["tenant_id"],
            UserTenantMembership.status == "ACTIVE",
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="INVALID_MEMBERSHIP")

    claims = {
        "user_id": str(user.id),
        "tenant_id": str(membership.tenant_id),
        "membership_id": str(membership.id),
        "role": membership.role,
    }
    access = create_access_token(user.email, extra_claims=claims)
    refresh = create_refresh_token(user.email, extra_claims=claims)
    return TokenResponse(access_token=access, refresh_token=refresh, role=membership.role)
