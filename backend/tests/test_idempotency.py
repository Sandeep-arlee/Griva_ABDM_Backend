import base64
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db, verify_abdm_signature
from app.core.config import settings
from app.main import app
from app.models.audit_log import AuditLog
from app.models.consent import Consent, ConsentStatus
from app.models.consent_event import ConsentEvent
from app.models.health_information_event import HealthInformationEvent
from app.models.health_information_request import HealthInformationRequest as HIRequest
from app.models.idempotency_key import IdempotencyKey
from app.models.patient import Patient
from app.services.abha_service import link_abha_to_patient


TENANT_ID = "00000000-0000-0000-0000-000000000001"
TENANT_UUID = uuid.UUID(TENANT_ID)


@pytest.fixture()
def seeded_db_session(db_session):
    db_session.info["tenant_id"] = TENANT_UUID
    settings.tenant_master_key_b64 = base64.b64encode(b"\x01" * 32).decode()
    with open("backend/abdm_private_key.pem", "r", encoding="utf-8") as handle:
        settings.abdm_private_key_pem = handle.read()
    settings.abdm_key_id = "test-key"
    patient = db_session.query(Patient).filter(Patient.patient_id == "abha-123").first()
    if not patient:
        patient = Patient(tenant_id=TENANT_UUID, patient_id="abha-123")
        db_session.add(patient)
        db_session.commit()
    link_abha_to_patient(db_session, TENANT_UUID, patient.id, abha_address="abha-123", abha_number=None)
    yield db_session


@pytest.fixture()
def client(seeded_db_session):
    def _get_db_override():
        try:
            yield seeded_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_current_user] = lambda: object()
    app.dependency_overrides[verify_abdm_signature] = lambda: None
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _headers(request_id: str) -> dict:
    return {
        "X-Request-ID": request_id,
        "X-Timestamp": "2026-02-04T10:00:00Z",
        "X-Tenant-ID": TENANT_ID,
        "X-HIP-ID": "GRIVA_HIP",
        "X-HIU-ID": "GRIVA_HIU",
        "X-CM-ID": "CM_001",
    }


def _consent_payload(request_id: str, consent_id: str = "CONSENT-001") -> dict:
    return {
        "requestId": request_id,
        "timestamp": "2026-02-04T10:00:00Z",
        "notification": {
            "consentRequestId": "CR-123",
            "status": "GRANTED",
            "consentArtefacts": [
                {
                    "id": consent_id,
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
            ],
        },
    }


def _seed_granted_consent(db_session, consent_id: str) -> Consent:
    existing = db_session.query(Consent).filter(Consent.abdm_consent_id == consent_id).first()
    if existing:
        return existing
    now = datetime.now(timezone.utc)
    consent = Consent(
        tenant_id=TENANT_UUID,
        abdm_consent_id=consent_id,
        patient_id="abha-123",
        hiu_id="GRIVA_HIU",
        hip_id="GRIVA_HIP",
        status=ConsentStatus.GRANTED,
        valid_from=now - timedelta(days=1),
        valid_to=now + timedelta(days=1),
        raw_payload=_consent_payload("req-consent", consent_id=consent_id),
    )
    db_session.add(consent)
    db_session.flush()
    db_session.add(
        ConsentEvent(
            tenant_id=TENANT_UUID,
            consent_id=consent.id,
            old_status=ConsentStatus.GRANTED,
            new_status=ConsentStatus.GRANTED,
            event_type=ConsentStatus.GRANTED,
            event_payload={"status": "GRANTED"},
        )
    )
    db_session.commit()
    return consent


def _hi_request_payload(request_id: str, consent_id: str) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "transactionId": "tx-001",
        "consentId": consent_id,
        "hiRequest": {
            "requestId": request_id,
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "hiTypes": ["OPConsultation"],
            "dateRange": {
                "from": (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
                "to": (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            },
        },
    }


def test_duplicate_consent_notify_idempotent(client, seeded_db_session):
    request_id = "req-idem-consent"
    payload = _consent_payload(request_id)

    resp1 = client.post("/abdm/consent/notify", json=payload, headers=_headers(request_id))
    assert resp1.status_code == 202

    resp2 = client.post("/abdm/consent/notify", json=payload, headers=_headers(request_id))
    assert resp2.status_code == 202
    assert resp2.json() == resp1.json()

    assert seeded_db_session.query(ConsentEvent).count() == 1
    assert (
        seeded_db_session.query(AuditLog)
        .filter(AuditLog.event_type == "ABDM_CONSENT_NOTIFY")
        .count()
        == 1
    )
    assert seeded_db_session.query(IdempotencyKey).count() == 1


def test_duplicate_hi_request_idempotent(client, seeded_db_session):
    consent = _seed_granted_consent(seeded_db_session, "CONSENT-REQ-1")
    request_id = "req-idem-hi"
    payload = _hi_request_payload(request_id, consent.abdm_consent_id)

    resp1 = client.post("/abdm/health-information/request", json=payload, headers=_headers(request_id))
    assert resp1.status_code == 202

    resp2 = client.post("/abdm/health-information/request", json=payload, headers=_headers(request_id))
    assert resp2.status_code == 202
    assert resp2.json() == resp1.json()

    assert seeded_db_session.query(HIRequest).count() == 1
    assert (
        seeded_db_session.query(HealthInformationEvent)
        .filter(HealthInformationEvent.event_type == "REQUESTED")
        .count()
        == 1
    )
    assert (
        seeded_db_session.query(AuditLog)
        .filter(AuditLog.event_type == "ABDM_HI_REQUEST")
        .count()
        == 1
    )
    assert seeded_db_session.query(IdempotencyKey).count() == 1
