import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.main import app
from app.models.user import User


TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class DummyUser:
    def __init__(self, user_id, role):
        self.id = user_id
        self.role = role


@pytest.fixture()
def client(db_session):
    def _get_db_override():
        try:
            yield db_session
        finally:
            pass

    db_session.info["tenant_id"] = TENANT_ID
    user = User(email="admin@test.local", hashed_password="x", role="ADMIN", is_active=True, tenant_id=TENANT_ID)
    db_session.add(user)
    db_session.commit()
    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_current_user] = lambda: DummyUser(user.id, "ADMIN")
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _headers():
    return {"X-Tenant-ID": str(TENANT_ID)}


def test_grant_and_enforce_internal_consent(client):
    payload = {"patient_id": "patient-1", "purpose": "CARE"}
    resp = client.post("/api/internal-consents/grant", json=payload, headers=_headers())
    assert resp.status_code == 201
    assert resp.json()["status"] == "GRANTED"

    # now access should pass (returns empty list)
    resp2 = client.get("/api/patients/patient-1/records", headers=_headers())
    assert resp2.status_code == 200


def test_revoke_blocks_access(client):
    grant_payload = {"patient_id": "patient-1", "purpose": "CARE"}
    grant = client.post("/api/internal-consents/grant", json=grant_payload, headers=_headers())
    assert grant.status_code == 201
    payload = {"patient_id": "patient-1", "purpose": "CARE", "reason": "patient request"}
    resp = client.post("/api/internal-consents/revoke", json=payload, headers=_headers())
    assert resp.status_code == 200
    assert resp.json()["status"] == "REVOKED"

    # access now blocked
    resp2 = client.get("/api/patients/patient-1/records", headers=_headers())
    assert resp2.status_code == 403
