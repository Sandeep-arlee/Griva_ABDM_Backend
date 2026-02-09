import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.db.base import Base
from app.main import app


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@pytest.fixture(scope="module")
def db_session():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def client(db_session):
    def _get_db_override():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _payload(artefact):
    return {
        "requestId": "req-001",
        "timestamp": "2026-02-04T10:00:00Z",
        "notification": {
            "consentRequestId": "CR-123",
            "status": "GRANTED",
            "consentArtefacts": [artefact],
        },
    }


def _artefact():
    return {
        "id": "CONSENT-001",
        "patient": {"id": "abha-123"},
        "hiu": {"id": "GRIVA_HIU"},
        "hip": {"id": "GRIVA_HIP"},
        "purpose": {"code": "CAREMGT", "refUri": "https://abdm.gov.in/purpose"},
        "hiTypes": ["OPConsultation"],
        "permission": {
            "accessMode": "VIEW",
            "dateRange": {"from": "2026-01-01T00:00:00Z", "to": "2026-12-31T23:59:59Z"},
            "frequency": {"unit": "HOUR", "value": 1, "repeats": 1},
            "dataEraseAt": "2027-01-01T00:00:00Z",
        },
    }


def _headers():
    return {
        "X-Request-ID": "req-001",
        "X-Timestamp": "2026-02-04T10:00:00Z",
        "X-HIP-ID": "GRIVA_HIP",
        "X-HIU-ID": "GRIVA_HIU",
        "X-CM-ID": "CM_001",
    }


def test_consent_notify_accepts_direct_artefact(client):
    response = client.post("/abdm/consent/notify", json=_payload(_artefact()), headers=_headers())
    assert response.status_code == 202


def test_consent_notify_accepts_wrapped_artefact(client):
    wrapper = {"id": "REF-001", "artefact": _artefact()}
    response = client.post("/abdm/consent/notify", json=_payload(wrapper), headers=_headers())
    assert response.status_code == 202
