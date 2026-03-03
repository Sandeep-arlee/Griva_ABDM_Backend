import os
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_user, get_db, verify_abdm_signature
from app.db.base import Base
from app.main import app
from app.models.consent import Consent, ConsentStatus
from app.models.tenant import Tenant


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
TENANT_ID = "00000000-0000-0000-0000-000000000001"
TENANT_UUID = uuid.UUID(TENANT_ID)


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
    if not db.query(Tenant).filter(Tenant.id == TENANT_UUID).first():
        db.add(Tenant(id=TENANT_UUID, name="Test Tenant"))
        db.commit()
    db.info["tenant_id"] = TENANT_UUID
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
    app.dependency_overrides[get_current_user] = lambda: object()
    app.dependency_overrides[verify_abdm_signature] = lambda: None
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
        "X-Tenant-ID": TENANT_ID,
        "X-HIP-ID": "GRIVA_HIP",
        "X-HIU-ID": "GRIVA_HIU",
        "X-CM-ID": "CM_001",
    }

def _parse_iso(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _seed_consent(db_session, artefact) -> None:
    existing = db_session.query(Consent).filter(Consent.abdm_consent_id == artefact["id"]).first()
    if existing:
        return
    date_range = artefact["permission"]["dateRange"]
    consent = Consent(
        tenant_id=TENANT_UUID,
        abdm_consent_id=artefact["id"],
        patient_id=artefact["patient"]["id"],
        hiu_id=artefact["hiu"]["id"],
        hip_id=artefact["hip"]["id"],
        status=ConsentStatus.GRANTED,
        valid_from=_parse_iso(date_range["from"]),
        valid_to=_parse_iso(date_range["to"]),
        raw_payload=_payload(artefact),
    )
    db_session.add(consent)
    db_session.commit()


def test_consent_notify_accepts_direct_artefact(client, db_session):
    artefact = _artefact()
    _seed_consent(db_session, artefact)
    response = client.post("/abdm/consent/notify", json=_payload(artefact), headers=_headers())
    assert response.status_code == 202


def test_consent_notify_accepts_wrapped_artefact(client, db_session):
    artefact = _artefact()
    _seed_consent(db_session, artefact)
    wrapper = {"id": "REF-001", "artefact": artefact}
    response = client.post("/abdm/consent/notify", json=_payload(wrapper), headers=_headers())
    assert response.status_code == 202
