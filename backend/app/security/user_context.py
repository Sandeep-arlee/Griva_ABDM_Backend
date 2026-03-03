from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from app.models.user import User


@dataclass(frozen=True)
class AuthenticatedUser:
    id: uuid.UUID
    role: str
    tenant_id: Optional[str] = None
    membership_id: Optional[str] = None


@dataclass(frozen=True)
class PreTenantUser:
    id: str
    role: None = None
    tenant_id: None = None
    membership_id: None = None


def _is_user_active(user: User) -> bool:
    status = getattr(user, "status", None)
    if status is not None:
        return status == "ACTIVE"
    return bool(getattr(user, "is_active", False))


def _parse_user_uuid(raw_id: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(raw_id))
    except ValueError:
        return None


def _resolve_user(db: Session, payload: dict) -> User | None:
    user_id = payload.get("user_id")
    if user_id:
        user_uuid = _parse_user_uuid(user_id)
        if not user_uuid:
            return None
        return db.query(User).filter(User.id == user_uuid).first()

    subject = payload.get("sub")
    if subject:
        return db.query(User).filter(User.email == subject).first()
    return None


def build_authenticated_user(
    db: Session,
    payload: dict,
    *,
    require_role: bool = False,
    require_membership: bool = False,
) -> AuthenticatedUser | None:
    user = _resolve_user(db, payload)
    if not user or not _is_user_active(user):
        return None

    role = payload.get("role")
    tenant_id = payload.get("tenant_id")
    membership_id = payload.get("membership_id")

    if require_role and not role:
        return None
    if require_membership and (not tenant_id or not membership_id):
        return None

    return AuthenticatedUser(
        id=user.id,
        role=role or user.role,
        tenant_id=tenant_id,
        membership_id=membership_id,
    )
