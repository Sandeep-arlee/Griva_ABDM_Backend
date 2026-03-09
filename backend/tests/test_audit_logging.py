import base64
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db, verify_abdm_signature
from app.core.config import settings
from app.main import app
from app.models.audit_log import AuditLog
from app.models.internal_consent import InternalConsent
from app.models.patient import Patient
from app.services.abha_service import link_abha_to_patient
from app.security.user_context import AuthenticatedUser


TENANT_ID = "00000000-0000-0000-0000-000000000001"
TENANT_UUID = uuid.UUID(TENANT_ID)


@pytest.fixture()
def seeded_db_session(db_session):
    db_session.info["tenant_id"] = TENANT_UUID
    settings.tenant_master_key_b64 = base64.b64encode(b"\x01" * 32).decode()
    with open("backend/abdm_private_key.pem", "r", encoding="utf-8") as handle:
        settings.abdm_private_key_pem = handle.read()
    settings.abdm_key_id = "test-key"
    yield db_session


@pytest.fixture()
def client(seeded_db_session):
    def _get_db_override():
        try:
            yield seeded_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        id=uuid.uuid4(),
        role="ADMIN",
        tenant_id=TENANT_ID,
        membership_id="mem-1",
    )
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


def test_audit_log_created_on_patient_and_record_create(client, seeded_db_session):
    patient_id = "patient-audit-1"
    seeded_db_session.add(
        InternalConsent(
            tenant_id=TENANT_UUID,
            subject_patient_id=patient_id,
            purpose="CARE",
            status="GRANTED",
            meta={},
        )
    )
    seeded_db_session.commit()

    response = client.post(
        "/api/records/upload",
        json={"patient_id": patient_id, "record_type": "OPConsultation", "uri": "s3://x"},
        headers={"X-Tenant-ID": TENANT_ID},
    )
    assert response.status_code == 200

    assert (
        seeded_db_session.query(AuditLog)
        .filter(AuditLog.action == "CREATE_PATIENT")
        .count()
        == 1
    )
    assert (
        seeded_db_session.query(AuditLog)
        .filter(AuditLog.action == "CREATE_MEDICAL_RECORD")
        .count()
        == 1
    )


def test_audit_log_created_on_consent_notify(client, seeded_db_session):
    patient = seeded_db_session.query(Patient).filter(Patient.patient_id == "abha-123").first()
    if not patient:
        patient = Patient(tenant_id=TENANT_UUID, patient_id="abha-123")
        seeded_db_session.add(patient)
        seeded_db_session.commit()
    link_abha_to_patient(seeded_db_session, TENANT_UUID, patient.id, abha_address="abha-123", abha_number=None)

    request_id = "req-audit-consent"
    payload = _consent_payload(request_id, consent_id="CONSENT-AUDIT-1")
    response = client.post("/abdm/consent/notify", json=payload, headers=_headers(request_id))
    assert response.status_code == 202

    assert (
        seeded_db_session.query(AuditLog)
        .filter(AuditLog.action == "ABDM_CONSENT_NOTIFY", AuditLog.request_id == request_id)
        .count()
        == 1
    )
