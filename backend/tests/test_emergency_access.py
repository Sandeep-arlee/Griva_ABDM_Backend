import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.models.consent import Consent, ConsentStatus
from app.models.emergency_access_v2 import EmergencyAccessSessionV2, EmergencyScopeType
from app.models.internal_consent import InternalConsent
from app.models.user import User
from app.models.user_tenant_membership import UserTenantMembership


TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
OTHER_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
SUPERADMIN_ID = uuid.UUID("00000000-0000-0000-0000-0000000000aa")
SUPERADMIN_EMAIL = "superadmin@test.local"
AUTH_TOKEN: str | None = None




@pytest.fixture()
def client(db_session):
    global AUTH_TOKEN
    super_admin = User(
        id=SUPERADMIN_ID,
        email=SUPERADMIN_EMAIL,
        hashed_password="x",
        role="SUPERADMIN",
        is_active=True,
        tenant_id=TENANT_ID,
    )
    db_session.add(super_admin)
    membership = UserTenantMembership(
        id=uuid.uuid4(),
        user_id=super_admin.id,
        tenant_id=TENANT_ID,
        role="SUPERADMIN",
        status="ACTIVE",
    )
    db_session.add(membership)
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
    db_session.add(other_consent)
    db_session.commit()
    AUTH_TOKEN = create_access_token(
        str(super_admin.id),
        extra_claims={
            "user_id": str(super_admin.id),
            "tenant_id": str(TENANT_ID),
            "membership_id": str(membership.id),
            "role": "SUPERADMIN",
        },
    )

    with TestClient(app) as test_client:
        yield test_client


def _headers(tenant_id=TENANT_ID):
    headers = {"X-Tenant-ID": str(tenant_id)}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    return headers

def _grant_internal_consent(db_session, patient_id: str):
    consent = InternalConsent(
        tenant_id=TENANT_ID,
        subject_patient_id=patient_id,
        purpose="CARE",
        status="GRANTED",
        meta={},
    )
    db_session.add(consent)
    db_session.commit()


def _request_emergency_access(client, reason="Emergency access required"):
    payload = {"reason": reason, "duration_minutes": 30}
    return client.post("/admin/emergency-access/request", json=payload, headers=_headers())


def test_superadmin_blocked_without_emergency_session(client):
    resp = client.get("/api/patients/patient-1/records", headers=_headers())
    assert resp.status_code == 403
    assert resp.json()["detail"] == "EMERGENCY_ACCESS_REQUIRED"


def test_access_with_valid_session(client, db_session):
    _grant_internal_consent(db_session, "patient-1")
    resp = _request_emergency_access(client)
    assert resp.status_code == 201

    resp2 = client.get("/api/patients/patient-1/records", headers=_headers())
    assert resp2.status_code == 200


def test_no_tenant_filter_bypass(client, db_session):
    _grant_internal_consent(db_session, "patient-1")
    resp = _request_emergency_access(client)
    assert resp.status_code == 201
    resp = client.get("/api/patients/patient-1/records", headers=_headers())
    assert resp.status_code == 200
    assert resp.json() == []


def test_cannot_access_different_tenant(client):
    resp = client.get("/api/patients/patient-1/records", headers=_headers(OTHER_TENANT_ID))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "EMERGENCY_ACCESS_REQUIRED"


def test_overlapping_sessions_prevented(client, db_session):
    now = datetime.now(timezone.utc)
    db_session.query(EmergencyAccessSessionV2).filter(
        EmergencyAccessSessionV2.tenant_id == TENANT_ID,
        EmergencyAccessSessionV2.revoked_at.is_(None),
        EmergencyAccessSessionV2.expires_at > now,
    ).update({EmergencyAccessSessionV2.revoked_at: now})
    db_session.commit()

    first = _request_emergency_access(client, reason="Overlap prevention test")
    assert first.status_code == 201

    resp = _request_emergency_access(client, reason="Overlap prevention test")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "EMERGENCY_ACCESS_ACTIVE"


def test_expired_session_blocks_access(client, db_session):
    now = datetime.now(timezone.utc)
    db_session.query(EmergencyAccessSessionV2).filter(
        EmergencyAccessSessionV2.tenant_id == TENANT_ID,
        EmergencyAccessSessionV2.revoked_at.is_(None),
        EmergencyAccessSessionV2.expires_at > now,
    ).update({EmergencyAccessSessionV2.revoked_at: now})
    db_session.commit()

    expired = EmergencyAccessSessionV2(
        tenant_id=TENANT_ID,
        super_admin_id=SUPERADMIN_ID,
        scope_type=EmergencyScopeType.TENANT_WIDE,
        scope_patient_id=None,
        reason="Expired session",
        requested_at=now - timedelta(hours=2),
        approved_at=now - timedelta(hours=2),
        expires_at=now - timedelta(hours=1),
        revoked_at=None,
        created_ip="127.0.0.1",
        created_user_agent="pytest",
        decrypt_count=0,
        export_count=0,
        export_payload_bytes=0,
        last_used_at=None,
    )
    db_session.add(expired)
    db_session.commit()

    resp = client.get("/api/patients/patient-1/records", headers=_headers())
    assert resp.status_code == 403
    assert resp.json()["detail"] == "EMERGENCY_ACCESS_REQUIRED"


def test_revoke_blocks_access(client):
    resp = client.post("/admin/emergency-access/request", json={"reason": "Revoke test"}, headers=_headers())
    assert resp.status_code == 201
    session_id = resp.json()["id"]

    revoke_resp = client.post(f"/admin/emergency-access/revoke/{session_id}", headers=_headers())
    assert revoke_resp.status_code == 200

    resp2 = client.get("/api/patients/patient-1/records", headers=_headers())
    assert resp2.status_code == 403
    assert resp2.json()["detail"] == "EMERGENCY_ACCESS_REQUIRED"


def test_consent_still_required(client):
    resp = client.post("/admin/emergency-access/request", json={"reason": "Consent check"}, headers=_headers())
    assert resp.status_code == 201

    resp2 = client.get("/api/patients/patient-1/records", headers=_headers())
    assert resp2.status_code == 403
    assert resp2.json()["detail"] == "INTERNAL_CONSENT_REQUIRED"
