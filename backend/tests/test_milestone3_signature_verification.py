import hashlib
import json
import sys
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.signature import canonicalize_request, hash_body
from app.main import app
from app.models.audit_log import AuditLog
from app.models.consent import Consent, ConsentStatus
from app.models.consent_event import ConsentEvent
from app.models.patient import Patient
from app.models.patient_abha_link import PatientAbhaLink
from app.models.trusted_key import TrustedKey
from app.models.trusted_request import TrustedRequest
TENANT_ID = "00000000-0000-0000-0000-000000000001"
TENANT_UUID = uuid.UUID(TENANT_ID)


def _generate_keys():
    private_key = ec.generate_private_key(ec.SECP256R1())
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    pub_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return priv_pem, pub_pem, private_key


@pytest.fixture()
def client(db_session):
    def _get_db_override():
        db_session.info["tenant_id"] = TENANT_UUID
        try:
            yield db_session
        finally:
            db_session.info.pop("tenant_id", None)

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_current_user] = lambda: object()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _clean_db(db_session):
    db_session.query(ConsentEvent).delete()
    db_session.query(Consent).delete()
    db_session.query(TrustedRequest).delete()
    db_session.query(TrustedKey).delete()
    db_session.query(AuditLog).delete()
    db_session.commit()
    yield


@pytest.fixture
def override_settings():
    old_priv = settings.abdm_private_key_pem
    old_key = settings.abdm_key_id
    old_tol = settings.abdm_timestamp_tolerance_seconds
    try:
        yield
    finally:
        settings.abdm_private_key_pem = old_priv
        settings.abdm_key_id = old_key
        settings.abdm_timestamp_tolerance_seconds = old_tol


def _payload(request_id: str, timestamp: str) -> dict:
    return {
        "requestId": request_id,
        "timestamp": timestamp,
        "notification": {
            "consentRequestId": "CR-123",
            "status": "GRANTED",
            "consentArtefacts": [
                {
                    "id": "CONSENT-001",
                    "patient": {"id": "abha-123"},
                    "hiu": {"id": "HIU123"},
                    "hip": {"id": "HIP123"},
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

def _parse_iso(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _seed_consent(db_session, payload: dict) -> None:
    artefact = payload["notification"]["consentArtefacts"][0]
    _ensure_abha_link(db_session, artefact["patient"]["id"])
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
        status=ConsentStatus(payload["notification"]["status"]),
        valid_from=_parse_iso(date_range["from"]),
        valid_to=_parse_iso(date_range["to"]),
        raw_payload=payload,
    )
    db_session.add(consent)
    db_session.commit()


def _ensure_abha_link(db_session, abha: str) -> None:
    normalized = abha.strip().lower()
    abha_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    patient = db_session.query(Patient).filter(Patient.patient_id == abha).first()
    if not patient:
        patient = Patient(tenant_id=TENANT_UUID, patient_id=abha)
        db_session.add(patient)
        db_session.flush()
    link = (
        db_session.query(PatientAbhaLink)
        .filter(PatientAbhaLink.tenant_id == TENANT_UUID, PatientAbhaLink.abha_hash == abha_hash)
        .first()
    )
    if not link:
        db_session.add(
            PatientAbhaLink(
                tenant_id=TENANT_UUID,
                patient_id=patient.id,
                abha_hash=abha_hash,
                link_status="VERIFIED",
            )
        )
    db_session.commit()


def _json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sign(private_key, method, path, request_id, timestamp, body_bytes):
    body_hash = hash_body(body_bytes)
    canonical = canonicalize_request(method, path, request_id, timestamp, body_hash)
    return private_key.sign(canonical, ec.ECDSA(hashes.SHA256()))


def _b64(signature):
    import base64

    return base64.b64encode(signature).decode("utf-8")


def _headers(signature, key_id, request_id, timestamp):
    return {
        "X-Signature": signature,
        "X-Key-Id": key_id,
        "X-Request-ID": request_id,
        "X-Timestamp": timestamp,
        "X-Tenant-ID": TENANT_ID,
        "X-HIP-ID": "HIP123",
        "X-HIU-ID": "HIU123",
        "X-CM-ID": "CM_001",
        "Content-Type": "application/json",
    }


def _audit_for(db_session, request_id: str):
    return (
        db_session.query(AuditLog)
        .filter(AuditLog.request_id == request_id, AuditLog.event_type == "ABDM_SIGNATURE")
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .first()
    )


def _counts(db_session):
    return {
        "consents": db_session.query(Consent).count(),
        "consent_events": db_session.query(ConsentEvent).count(),
        "trusted_requests": db_session.query(TrustedRequest).count(),
    }


def test_valid_signed_request_returns_202(client, db_session, override_settings):
    priv_pem, pub_pem, private_key = _generate_keys()
    key_id = f"KEY-{uuid.uuid4()}"
    db_session.add(TrustedKey(tenant_id=TENANT_UUID, key_id=key_id, public_key=pub_pem, is_active=True))
    db_session.commit()

    settings.abdm_private_key_pem = priv_pem
    settings.abdm_key_id = key_id

    request_id = "req-001"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = _payload(request_id, timestamp)
    _seed_consent(db_session, payload)
    body = _json_bytes(payload)
    sig = _b64(_sign(private_key, "POST", "/abdm/consent/notify", request_id, timestamp, body))

    resp = client.post(
        "/abdm/consent/notify",
        content=body,
        headers=_headers(sig, key_id, request_id, timestamp),
    )
    assert resp.status_code == 202

    audit = _audit_for(db_session, request_id)
    assert audit is not None
    assert audit.meta.get("outcome") == "SIGNATURE_OK"
    counts = _counts(db_session)
    assert counts["consents"] == 1
    assert counts["consent_events"] == 1


def test_replay_returns_202(client, db_session, override_settings):
    priv_pem, pub_pem, private_key = _generate_keys()
    key_id = f"KEY-{uuid.uuid4()}"
    db_session.add(TrustedKey(tenant_id=TENANT_UUID, key_id=key_id, public_key=pub_pem, is_active=True))
    db_session.commit()

    settings.abdm_private_key_pem = priv_pem
    settings.abdm_key_id = key_id

    request_id = "req-replay"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = _payload(request_id, timestamp)
    _seed_consent(db_session, payload)
    body = _json_bytes(payload)
    sig = _b64(_sign(private_key, "POST", "/abdm/consent/notify", request_id, timestamp, body))

    resp1 = client.post(
        "/abdm/consent/notify",
        content=body,
        headers=_headers(sig, key_id, request_id, timestamp),
    )
    assert resp1.status_code == 202

    resp2 = client.post(
        "/abdm/consent/notify",
        content=body,
        headers=_headers(sig, key_id, request_id, timestamp),
    )
    assert resp2.status_code == 202
    assert resp2.json() == resp1.json()

    audit = _audit_for(db_session, request_id)
    assert audit is not None
    assert audit.meta.get("outcome") == "REPLAY_DETECTED"
    counts = _counts(db_session)
    assert counts["consents"] == 1
    assert counts["consent_events"] == 1


def test_missing_signature_header_returns_401(client, db_session, override_settings):
    request_id = "req-missing"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = _payload(request_id, timestamp)
    body = _json_bytes(payload)
    headers = _headers("", "", request_id, timestamp)
    headers.pop("X-Signature")

    resp = client.post("/abdm/consent/notify", content=body, headers=headers)
    assert resp.status_code == 401
    assert resp.json().get("detail") == "MISSING_SIGNATURE"

    audit = _audit_for(db_session, request_id)
    assert audit is not None
    assert audit.meta.get("outcome") == "MISSING_SIGNATURE"
    counts = _counts(db_session)
    assert counts["consents"] == 0
    assert counts["consent_events"] == 0


def test_invalid_signature_returns_401(client, db_session, override_settings):
    priv_pem, pub_pem, private_key = _generate_keys()
    key_id = f"KEY-{uuid.uuid4()}"
    db_session.add(TrustedKey(tenant_id=TENANT_UUID, key_id=key_id, public_key=pub_pem, is_active=True))
    db_session.commit()

    settings.abdm_private_key_pem = priv_pem
    settings.abdm_key_id = key_id

    request_id = "req-bad-sig"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = _payload(request_id, timestamp)
    body = _json_bytes(payload)
    sig = _b64(_sign(private_key, "POST", "/abdm/consent/notify", request_id, timestamp, body))

    tampered = _payload(request_id, timestamp)
    tampered["notification"]["consentRequestId"] = "TAMPERED"
    tampered_body = _json_bytes(tampered)

    resp = client.post(
        "/abdm/consent/notify",
        content=tampered_body,
        headers=_headers(sig, key_id, request_id, timestamp),
    )
    assert resp.status_code == 401
    assert resp.json().get("detail") == "INVALID_SIGNATURE"

    audit = _audit_for(db_session, request_id)
    assert audit is not None
    assert audit.meta.get("outcome") == "INVALID_SIGNATURE"
    counts = _counts(db_session)
    assert counts["consents"] == 0
    assert counts["consent_events"] == 0


def test_timestamp_outside_window_returns_401(client, db_session, override_settings):
    priv_pem, pub_pem, private_key = _generate_keys()
    key_id = f"KEY-{uuid.uuid4()}"
    db_session.add(TrustedKey(tenant_id=TENANT_UUID, key_id=key_id, public_key=pub_pem, is_active=True))
    db_session.commit()

    settings.abdm_private_key_pem = priv_pem
    settings.abdm_key_id = key_id
    settings.abdm_timestamp_tolerance_seconds = 300

    request_id = "req-old"
    old_ts = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    payload = _payload(request_id, old_ts)
    body = _json_bytes(payload)
    sig = _b64(_sign(private_key, "POST", "/abdm/consent/notify", request_id, old_ts, body))

    resp = client.post(
        "/abdm/consent/notify",
        content=body,
        headers=_headers(sig, key_id, request_id, old_ts),
    )
    assert resp.status_code == 401
    assert resp.json().get("detail") == "TIMESTAMP_OUT_OF_RANGE"

    audit = _audit_for(db_session, request_id)
    assert audit is not None
    assert audit.meta.get("outcome") == "TIMESTAMP_OUT_OF_RANGE"
    counts = _counts(db_session)
    assert counts["consents"] == 0
    assert counts["consent_events"] == 0


def test_invalid_key_id_returns_401(client, db_session, override_settings):
    priv_pem, pub_pem, private_key = _generate_keys()
    key_id = f"KEY-{uuid.uuid4()}"
    db_session.add(TrustedKey(tenant_id=TENANT_UUID, key_id=key_id, public_key=pub_pem, is_active=False))
    db_session.commit()

    settings.abdm_private_key_pem = priv_pem
    settings.abdm_key_id = key_id

    request_id = "req-unknown-key"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = _payload(request_id, timestamp)
    body = _json_bytes(payload)
    sig = _b64(_sign(private_key, "POST", "/abdm/consent/notify", request_id, timestamp, body))

    resp = client.post(
        "/abdm/consent/notify",
        content=body,
        headers=_headers(sig, key_id, request_id, timestamp),
    )
    assert resp.status_code == 401
    assert resp.json().get("detail") == "INVALID_SIGNATURE"

    audit = _audit_for(db_session, request_id)
    assert audit is not None
    assert audit.meta.get("outcome") == "INVALID_SIGNATURE"
    counts = _counts(db_session)
    assert counts["consents"] == 0
    assert counts["consent_events"] == 0
