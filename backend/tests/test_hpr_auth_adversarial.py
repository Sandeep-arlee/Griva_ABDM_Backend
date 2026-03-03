import base64
import os
import uuid
from urllib.parse import urlparse, parse_qs

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.db.base import Base
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User
from app.models.user_tenant_membership import UserTenantMembership
from app.services.hpr_oauth import decode_oauth_state
from app.routing.policy import _POLICY_REGISTRY


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
TENANT_A = uuid.UUID("00000000-0000-0000-0000-000000000001")
TENANT_B = uuid.UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture(scope="module")
def db_engine():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    if settings.database_url != TEST_DATABASE_URL:
        pytest.skip("DATABASE_URL must point to TEST_DATABASE_URL for integration tests")
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def db_session(db_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = SessionLocal()
    db.info["tenant_id"] = None
    db.add(Tenant(id=TENANT_A, name="Tenant A"))
    db.add(Tenant(id=TENANT_B, name="Tenant B"))
    db.commit()
    yield db
    db.close()


@pytest.fixture(autouse=True)
def _oauth_settings(monkeypatch):
    monkeypatch.setattr(settings, "hpr_oauth_auth_url", "https://example.test/auth")
    monkeypatch.setattr(settings, "hpr_oauth_token_url", "https://example.test/token")
    monkeypatch.setattr(settings, "hpr_oauth_jwks_url", "https://example.test/jwks")
    monkeypatch.setattr(settings, "hpr_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "hpr_oauth_client_secret", "client-secret")
    monkeypatch.setattr(settings, "hpr_oauth_redirect_uri", "https://example.test/callback")
    monkeypatch.setattr(settings, "hpr_oauth_issuer", "https://issuer.example.test")
    monkeypatch.setattr(settings, "hpr_oauth_cookie_secure", False)
    monkeypatch.setattr(settings, "platform_identity_key_b64", base64.b64encode(b"\x00" * 32).decode())


@pytest.fixture()
def client(db_engine):
    _POLICY_REGISTRY.clear()
    with TestClient(app) as test_client:
        yield test_client


def _extract_state(redirect_url: str) -> str:
    parsed = urlparse(redirect_url)
    params = parse_qs(parsed.query)
    return params["state"][0]


def _make_user_and_membership(db_session, *, role="SUPERADMIN", tenant_id=TENANT_A, status="ACTIVE"):
    user = User(
        id=uuid.uuid4(),
        email=f"user-{uuid.uuid4()}@example.test",
        hashed_password="x",
        role=role,
        is_active=True,
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.flush()
    membership = UserTenantMembership(
        id=uuid.uuid4(),
        user_id=user.id,
        tenant_id=tenant_id,
        role=role,
        status=status,
    )
    db_session.add(membership)
    db_session.commit()
    return user, membership


def test_hpr_callback_state_replay_rejected(client, monkeypatch):
    resp = client.get("/api/auth/hpr/start")
    assert resp.status_code == 200
    redirect_url = resp.json()["redirect_url"]
    state = _extract_state(redirect_url)
    cookie_name = settings.hpr_oauth_state_cookie_name
    state_cookie = client.cookies.get(cookie_name)
    assert state_cookie
    decoded = decode_oauth_state(state_cookie)

    def _exchange(code, verifier):
        assert verifier == decoded["verifier"]
        return {"id_token": "id-token"}

    def _validate(id_token):
        return {"sub": "hpr-1", "nonce": decoded["nonce"], "iss": settings.hpr_oauth_issuer}

    monkeypatch.setattr("app.api.routes.auth_hpr.exchange_code_for_token", _exchange)
    monkeypatch.setattr("app.api.routes.auth_hpr.validate_id_token", _validate)

    first = client.get("/api/auth/hpr/callback", params={"code": "code-1", "state": state})
    assert first.status_code == 200

    second = client.get("/api/auth/hpr/callback", params={"code": "code-1", "state": state})
    assert second.status_code == 401


def test_hpr_callback_nonce_mismatch(client, monkeypatch, db_session):
    resp = client.get("/api/auth/hpr/start")
    assert resp.status_code == 200
    redirect_url = resp.json()["redirect_url"]
    state = _extract_state(redirect_url)
    cookie_name = settings.hpr_oauth_state_cookie_name
    state_cookie = client.cookies.get(cookie_name)
    decoded = decode_oauth_state(state_cookie)

    def _exchange(code, verifier):
        return {"id_token": "id-token"}

    def _validate(id_token):
        return {"sub": "hpr-2", "nonce": "wrong", "iss": settings.hpr_oauth_issuer}

    monkeypatch.setattr("app.api.routes.auth_hpr.exchange_code_for_token", _exchange)
    monkeypatch.setattr("app.api.routes.auth_hpr.validate_id_token", _validate)

    resp2 = client.get("/api/auth/hpr/callback", params={"code": "code-2", "state": state})
    assert resp2.status_code == 401

    user = db_session.query(User).filter(User.hpr_id == "hpr-2").first()
    assert user is None


def test_pre_tenant_token_denied_on_tenant_route(client, monkeypatch):
    resp = client.get("/api/auth/hpr/start")
    state = _extract_state(resp.json()["redirect_url"])
    state_cookie = client.cookies.get(settings.hpr_oauth_state_cookie_name)
    decoded = decode_oauth_state(state_cookie)

    def _exchange(code, verifier):
        return {"id_token": "id-token"}

    def _validate(id_token):
        return {"sub": "hpr-3", "nonce": decoded["nonce"], "iss": settings.hpr_oauth_issuer}

    monkeypatch.setattr("app.api.routes.auth_hpr.exchange_code_for_token", _exchange)
    monkeypatch.setattr("app.api.routes.auth_hpr.validate_id_token", _validate)

    cb = client.get("/api/auth/hpr/callback", params={"code": "code-3", "state": state})
    pre_token = cb.json()["pre_tenant_token"]
    resp2 = client.get(
        "/governance/emergency/active",
        headers={"Authorization": f"Bearer {pre_token}", "X-Tenant-ID": str(TENANT_A)},
    )
    assert resp2.status_code == 403


def test_pre_tenant_token_denied_on_refresh(client, monkeypatch):
    resp = client.get("/api/auth/hpr/start")
    state = _extract_state(resp.json()["redirect_url"])
    state_cookie = client.cookies.get(settings.hpr_oauth_state_cookie_name)
    decoded = decode_oauth_state(state_cookie)

    def _exchange(code, verifier):
        return {"id_token": "id-token"}

    def _validate(id_token):
        return {"sub": "hpr-4", "nonce": decoded["nonce"], "iss": settings.hpr_oauth_issuer}

    monkeypatch.setattr("app.api.routes.auth_hpr.exchange_code_for_token", _exchange)
    monkeypatch.setattr("app.api.routes.auth_hpr.validate_id_token", _validate)

    cb = client.get("/api/auth/hpr/callback", params={"code": "code-4", "state": state})
    pre_token = cb.json()["pre_tenant_token"]
    resp2 = client.post("/api/auth/hpr/refresh", json={"refresh_token": pre_token})
    assert resp2.status_code == 401


def test_refresh_token_denied_on_tenant_route(db_session, client):
    user, membership = _make_user_and_membership(db_session, role="SUPERADMIN", tenant_id=TENANT_A)
    claims = {
        "user_id": str(user.id),
        "tenant_id": str(membership.tenant_id),
        "membership_id": str(membership.id),
        "role": membership.role,
    }
    refresh = create_refresh_token(str(user.id), extra_claims=claims)
    resp = client.get(
        "/governance/emergency/active",
        headers={"Authorization": f"Bearer {refresh}", "X-Tenant-ID": str(TENANT_A)},
    )
    assert resp.status_code == 403


def test_refresh_token_denied_on_select_tenant(db_session, client):
    user, membership = _make_user_and_membership(db_session, role="SUPERADMIN", tenant_id=TENANT_A)
    claims = {
        "user_id": str(user.id),
        "tenant_id": str(membership.tenant_id),
        "membership_id": str(membership.id),
        "role": membership.role,
    }
    refresh = create_refresh_token(str(user.id), extra_claims=claims)
    resp = client.post(
        "/api/auth/hpr/select-tenant",
        json={"tenant_id": str(TENANT_A)},
        headers={"Authorization": f"Bearer {refresh}"},
    )
    assert resp.status_code == 403


def test_access_token_tenant_mismatch(db_session, client):
    user, membership = _make_user_and_membership(db_session, role="SUPERADMIN", tenant_id=TENANT_A)
    claims = {
        "user_id": str(user.id),
        "tenant_id": str(membership.tenant_id),
        "membership_id": str(membership.id),
        "role": membership.role,
    }
    access = create_access_token(str(user.id), extra_claims=claims)
    resp = client.get(
        "/governance/emergency/active",
        headers={"Authorization": f"Bearer {access}", "X-Tenant-ID": str(TENANT_B)},
    )
    assert resp.status_code == 403


def test_refresh_rejected_if_user_disabled(db_session, client):
    user, membership = _make_user_and_membership(db_session, role="SUPERADMIN", tenant_id=TENANT_A)
    claims = {
        "user_id": str(user.id),
        "tenant_id": str(membership.tenant_id),
        "membership_id": str(membership.id),
        "role": membership.role,
    }
    refresh = create_refresh_token(str(user.id), extra_claims=claims)
    user.status = "DISABLED"
    db_session.commit()

    resp = client.post("/api/auth/hpr/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 403


def test_refresh_rejected_if_membership_suspended(db_session, client):
    user, membership = _make_user_and_membership(db_session, role="SUPERADMIN", tenant_id=TENANT_A)
    claims = {
        "user_id": str(user.id),
        "tenant_id": str(membership.tenant_id),
        "membership_id": str(membership.id),
        "role": membership.role,
    }
    refresh = create_refresh_token(str(user.id), extra_claims=claims)
    membership.status = "SUSPENDED"
    db_session.commit()

    resp = client.post("/api/auth/hpr/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 403


def test_membership_enumeration_blocked(db_session, client, monkeypatch):
    user_a, membership_a = _make_user_and_membership(db_session, role="DOCTOR", tenant_id=TENANT_A)
    user_b, membership_b = _make_user_and_membership(db_session, role="DOCTOR", tenant_id=TENANT_B)

    resp = client.get("/api/auth/hpr/start")
    state = _extract_state(resp.json()["redirect_url"])
    state_cookie = client.cookies.get(settings.hpr_oauth_state_cookie_name)
    decoded = decode_oauth_state(state_cookie)

    def _exchange(code, verifier):
        return {"id_token": "id-token"}

    def _validate(id_token):
        return {"sub": "hpr-user-a", "nonce": decoded["nonce"], "iss": settings.hpr_oauth_issuer}

    user_a.hpr_id = "hpr-user-a"
    db_session.commit()

    monkeypatch.setattr("app.api.routes.auth_hpr.exchange_code_for_token", _exchange)
    monkeypatch.setattr("app.api.routes.auth_hpr.validate_id_token", _validate)

    cb = client.get("/api/auth/hpr/callback", params={"code": "code-5", "state": state})
    pre_token = cb.json()["pre_tenant_token"]

    resp2 = client.get(
        "/api/auth/hpr/memberships",
        params={"user_id": str(user_b.id)},
        headers={"Authorization": f"Bearer {pre_token}"},
    )
    assert resp2.status_code == 200
    tenant_ids = {m["tenant_id"] for m in resp2.json()["memberships"]}
    assert str(membership_a.tenant_id) in tenant_ids
    assert str(membership_b.tenant_id) not in tenant_ids


def test_membership_loader_criteria_respected(db_engine, db_session):
    user, membership_a = _make_user_and_membership(db_session, role="DOCTOR", tenant_id=TENANT_A)
    _make_user_and_membership(db_session, role="DOCTOR", tenant_id=TENANT_B)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    db = SessionLocal()
    db.info["tenant_id"] = TENANT_B
    memberships = db.query(UserTenantMembership).all()
    db.close()

    assert all(m.tenant_id == TENANT_B for m in memberships)
