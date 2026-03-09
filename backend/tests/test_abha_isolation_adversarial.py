import base64
import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db, verify_abdm_signature
from app.core.config import settings
from app.main import app
from app.models.patient import Patient
from app.services.abha_service import get_patient_by_abha, link_abha_to_patient
from app.routing.policy import _POLICY_REGISTRY


TENANT_A = uuid.UUID("00000000-0000-0000-0000-000000000001")
TENANT_B = uuid.UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture(autouse=True)
def _abdm_settings():
    settings.tenant_master_key_b64 = base64.b64encode(b"\x01" * 32).decode()
    with open("backend/abdm_private_key.pem", "r", encoding="utf-8") as handle:
        settings.abdm_private_key_pem = handle.read()
    settings.abdm_key_id = "test-key"


@pytest.fixture()
def client(db_session):
    def _get_db_override():
        try:
            yield db_session
        finally:
            pass

    _POLICY_REGISTRY.clear()
    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_current_user] = lambda: object()
    app.dependency_overrides[verify_abdm_signature] = lambda: None
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _payload(abha_id: str):
    return {
        "requestId": "req-001",
        "timestamp": "2026-02-04T10:00:00Z",
        "notification": {
            "consentRequestId": "CR-123",
            "status": "GRANTED",
            "consentArtefacts": [
                {
                    "id": "CONSENT-001",
                    "patient": {"id": abha_id},
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


def _headers(tenant_id: str):
    return {
        "X-Request-ID": "req-001",
        "X-Timestamp": "2026-02-04T10:00:00Z",
        "X-Tenant-ID": tenant_id,
        "X-HIP-ID": "GRIVA_HIP",
        "X-HIU-ID": "GRIVA_HIU",
        "X-CM-ID": "CM_001",
    }


def _create_patient(db, tenant_id: uuid.UUID, patient_id: str) -> Patient:
    db.info["tenant_id"] = tenant_id
    patient = Patient(tenant_id=tenant_id, patient_id=patient_id)
    db.add(patient)
    db.commit()
    return patient


def test_cross_tenant_lookup_blocked(db_session):
    patient = _create_patient(db_session, TENANT_A, "PAT-A")
    db_session.info["tenant_id"] = TENANT_A
    link_abha_to_patient(db_session, TENANT_A, patient.id, abha_address="abha@abdm", abha_number=None)
    db_session.info["tenant_id"] = TENANT_B
    assert get_patient_by_abha(db_session, TENANT_B, "abha@abdm") is None


def test_consent_with_unlinked_abha_rejected(client, db_session):
    db_session.info["tenant_id"] = TENANT_A
    resp = client.post(
        "/abdm/consent/notify",
        json=_payload("unlinked@abdm"),
        headers=_headers(str(TENANT_A)),
    )
    assert resp.status_code == 400
    assert resp.json().get("detail") == "PATIENT_NOT_LINKED"


def test_duplicate_abha_same_tenant(db_session):
    patient = _create_patient(db_session, TENANT_A, "PAT-DUP")
    db_session.info["tenant_id"] = TENANT_A
    link_abha_to_patient(db_session, TENANT_A, patient.id, abha_address="dup@abdm", abha_number=None)
    with pytest.raises(ValueError):
        link_abha_to_patient(db_session, TENANT_A, patient.id, abha_address="dup@abdm", abha_number=None)


def test_same_abha_different_tenants_allowed(db_session):
    patient_a = _create_patient(db_session, TENANT_A, "PAT-A2")
    patient_b = _create_patient(db_session, TENANT_B, "PAT-B2")
    db_session.info["tenant_id"] = TENANT_A
    link_abha_to_patient(db_session, TENANT_A, patient_a.id, abha_address="shared@abdm", abha_number=None)
    db_session.info["tenant_id"] = TENANT_B
    link_abha_to_patient(db_session, TENANT_B, patient_b.id, abha_address="shared@abdm", abha_number=None)
