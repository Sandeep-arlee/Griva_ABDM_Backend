import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.db.base import Base
from app.main import app
from app.models.consent import Consent, ConsentStatus
from app.models.emergency_access_session import EmergencyAccessSession
from app.models.tenant import Tenant
from app.models.user import User
from app.tenancy import get_current_tenant_id


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
OTHER_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
SUPERADMIN_ID = uuid.UUID("00000000-0000-0000-0000-0000000000aa")
SUPERADMIN_EMAIL = "superadmin@test.local"


class DummyUser:
    def __init__(self, user_id, role):
        self.id = user_id
        self.role = role


@pytest.fixture(scope="module")
def db_session():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    db.info["tenant_id"] = None
    db.add(Tenant(id=TENANT_ID, name="Tenant A"))
    db.add(Tenant(id=OTHER_TENANT_ID, name="Tenant B"))
    db.commit()
    super_admin = User(
        id=SUPERADMIN_ID,
        email=SUPERADMIN_EMAIL,
        hashed_password="x",
        role="SUPERADMIN",
        is_active=True,
        tenant_id=TENANT_ID,
    )
    db.add(super_admin)
    now = datetime.now(timezone.utc)
    other_consent = Consent(
        tenant_id=OTHER_TENANT_ID,
        abdm_consent_id="consent-other",
        patient_id="patient-other",
        hiu_id="hiu",
        hip_id="hip",
        status=ConsentStatus.GRANTED,
        valid_from=now,
        valid_to=now + timedelta(days=1),
        raw_payload={},
    )
    db.add(other_consent)
    db.commit()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def client(db_session):
    def _get_db_override():
        tenant_id = get_current_tenant_id()
        if settings.strict_tenant_mode and not tenant_id:
            raise HTTPException(status_code=400, detail="TENANT_REQUIRED")
        if tenant_id:
            exists = db_session.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not exists:
                raise HTTPException(status_code=400, detail="TENANT_NOT_FOUND")
            db_session.info["tenant_id"] = tenant_id
        try:
            yield db_session
        finally:
            db_session.info.pop("tenant_id", None)

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_current_user] = lambda: DummyUser(SUPERADMIN_ID, "SUPERADMIN")
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _headers(tenant_id=TENANT_ID):
    return {"X-Tenant-ID": str(tenant_id)}


def _request_emergency_access(client, reason="Emergency access required"):
    payload = {"reason": reason, "duration_minutes": 30}
    return client.post("/admin/emergency-access/request", json=payload, headers=_headers())


def test_superadmin_blocked_without_emergency_session(client):
    resp = client.get("/api/consents", headers=_headers())
    assert resp.status_code == 403
    assert resp.json()["detail"] == "EMERGENCY_ACCESS_REQUIRED"


def test_access_with_valid_session(client):
    resp = _request_emergency_access(client)
    assert resp.status_code == 201

    resp2 = client.get("/api/consents", headers=_headers())
    assert resp2.status_code == 200


def test_no_tenant_filter_bypass(client):
    resp = client.get("/api/consents", headers=_headers())
    assert resp.status_code == 200
    assert resp.json() == []


def test_cannot_access_different_tenant(client):
    resp = client.get("/api/consents", headers=_headers(OTHER_TENANT_ID))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "EMERGENCY_ACCESS_REQUIRED"


def test_overlapping_sessions_prevented(client, db_session):
    now = datetime.now(timezone.utc)
    db_session.query(EmergencyAccessSession).filter(
        EmergencyAccessSession.tenant_id == TENANT_ID,
        EmergencyAccessSession.revoked_at.is_(None),
        EmergencyAccessSession.expires_at > now,
    ).update({EmergencyAccessSession.revoked_at: now})
    db_session.commit()

    first = _request_emergency_access(client, reason="Overlap prevention test")
    assert first.status_code == 201

    resp = _request_emergency_access(client, reason="Overlap prevention test")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "EMERGENCY_ACCESS_ACTIVE"


def test_expired_session_blocks_access(client, db_session):
    now = datetime.now(timezone.utc)
    db_session.query(EmergencyAccessSession).filter(
        EmergencyAccessSession.tenant_id == TENANT_ID,
        EmergencyAccessSession.revoked_at.is_(None),
        EmergencyAccessSession.expires_at > now,
    ).update({EmergencyAccessSession.revoked_at: now})
    db_session.commit()

    expired = EmergencyAccessSession(
        tenant_id=TENANT_ID,
        super_admin_id=SUPERADMIN_ID,
        reason="Expired session",
        approved_by=None,
        approved_at=None,
        created_at=now - timedelta(hours=2),
        expires_at=now - timedelta(hours=1),
        revoked_at=None,
    )
    db_session.add(expired)
    db_session.commit()

    resp = client.get("/api/consents", headers=_headers())
    assert resp.status_code == 403
    assert resp.json()["detail"] == "EMERGENCY_ACCESS_REQUIRED"


def test_revoke_blocks_access(client):
    resp = client.post("/admin/emergency-access/request", json={"reason": "Revoke test"}, headers=_headers())
    assert resp.status_code == 201
    session_id = resp.json()["id"]

    revoke_resp = client.post(f"/admin/emergency-access/revoke/{session_id}", headers=_headers())
    assert revoke_resp.status_code == 200

    resp2 = client.get("/api/consents", headers=_headers())
    assert resp2.status_code == 403
    assert resp2.json()["detail"] == "EMERGENCY_ACCESS_REQUIRED"


def test_consent_still_required(client):
    resp = client.post("/admin/emergency-access/request", json={"reason": "Consent check"}, headers=_headers())
    assert resp.status_code == 201

    resp2 = client.get("/api/patients/patient-1/records", headers=_headers())
    assert resp2.status_code == 403
    assert resp2.json()["detail"] == "INTERNAL_CONSENT_REQUIRED"
