import uuid
from datetime import datetime, timedelta, timezone

import hashlib
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.signature import canonicalize_request, hash_body
from app.main import app
from app.models.consent import Consent, ConsentStatus
from app.models.consent_event import ConsentEvent
from app.models.patient import Patient
from app.models.patient_abha_link import PatientAbhaLink
from app.models.trusted_key import TrustedKey
from app.tenancy import get_current_tenant_id


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
        tenant_id = get_current_tenant_id()
        if settings.strict_tenant_mode and not tenant_id:
            raise HTTPException(status_code=400, detail="TENANT_REQUIRED")
        if tenant_id:
            db_session.info["tenant_id"] = tenant_id
        try:
            yield db_session
        finally:
            db_session.info.pop("tenant_id", None)

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_current_user] = lambda: object()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _payload(timestamp: str | None = None):
    ts = timestamp or _now_iso()
    return {
        "requestId": "req-001",
        "timestamp": ts,
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


def _sign(private_key, method, path, request_id, timestamp, body_bytes):
    body_hash = hash_body(body_bytes)
    canonical = canonicalize_request(method, path, request_id, timestamp, body_hash)
    signature = private_key.sign(canonical, ec.ECDSA(hashes.SHA256()))
    return signature


def _b64(signature):
    import base64

    return base64.b64encode(signature).decode("utf-8")


def _json_bytes(payload: dict) -> bytes:
    import json

    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def test_valid_signed_request_returns_202(client, db_session):
    priv_pem, pub_pem, private_key = _generate_keys()
    key_id = f"KEY-{uuid.uuid4()}"
    db_session.add(TrustedKey(tenant_id=TENANT_UUID, key_id=key_id, public_key=pub_pem, is_active=True))
    db_session.commit()

    settings.abdm_private_key_pem = priv_pem
    settings.abdm_key_id = key_id

    payload = _payload()
    _seed_consent(db_session, payload)
    body = _json_bytes(payload)
    timestamp = payload["timestamp"]
    sig = _b64(_sign(private_key, "POST", "/abdm/consent/notify", payload["requestId"], timestamp, body))

    resp = client.post("/abdm/consent/notify", content=body, headers=_headers(sig, key_id, payload["requestId"], timestamp))
    assert resp.status_code == 202


def test_replay_returns_202(client, db_session):
    priv_pem, pub_pem, private_key = _generate_keys()
    key_id = f"KEY-{uuid.uuid4()}"
    db_session.add(TrustedKey(tenant_id=TENANT_UUID, key_id=key_id, public_key=pub_pem, is_active=True))
    db_session.commit()

    settings.abdm_private_key_pem = priv_pem
    settings.abdm_key_id = key_id

    payload = _payload()
    _seed_consent(db_session, payload)
    body = _json_bytes(payload)
    timestamp = payload["timestamp"]
    sig = _b64(_sign(private_key, "POST", "/abdm/consent/notify", payload["requestId"], timestamp, body))

    resp1 = client.post("/abdm/consent/notify", content=body, headers=_headers(sig, key_id, payload["requestId"], timestamp))
    assert resp1.status_code == 202
    resp2 = client.post("/abdm/consent/notify", content=body, headers=_headers(sig, key_id, payload["requestId"], timestamp))
    assert resp2.status_code == 202
    assert resp2.json() == resp1.json()
    assert db_session.query(ConsentEvent).count() == 1


def test_tampered_body_returns_401(client, db_session):
    priv_pem, pub_pem, private_key = _generate_keys()
    key_id = f"KEY-{uuid.uuid4()}"
    db_session.add(TrustedKey(tenant_id=TENANT_UUID, key_id=key_id, public_key=pub_pem, is_active=True))
    db_session.commit()

    settings.abdm_private_key_pem = priv_pem
    settings.abdm_key_id = key_id

    payload = _payload()
    _seed_consent(db_session, payload)
    body = _json_bytes(payload)
    timestamp = payload["timestamp"]
    sig = _b64(_sign(private_key, "POST", "/abdm/consent/notify", payload["requestId"], timestamp, body))

    tampered = _payload(payload["timestamp"])
    tampered["notification"]["consentRequestId"] = "TAMPERED"
    tampered_body = _json_bytes(tampered)
    resp = client.post(
        "/abdm/consent/notify",
        content=tampered_body,
        headers=_headers(sig, key_id, payload["requestId"], timestamp),
    )
    assert resp.status_code == 401


def test_expired_timestamp_returns_401(client, db_session):
    priv_pem, pub_pem, private_key = _generate_keys()
    key_id = f"KEY-{uuid.uuid4()}"
    db_session.add(TrustedKey(tenant_id=TENANT_UUID, key_id=key_id, public_key=pub_pem, is_active=True))
    db_session.commit()

    settings.abdm_private_key_pem = priv_pem
    settings.abdm_key_id = key_id

    old_ts = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    payload = _payload(old_ts)
    _seed_consent(db_session, payload)
    body = _json_bytes(payload)
    sig = _b64(_sign(private_key, "POST", "/abdm/consent/notify", payload["requestId"], old_ts, body))

    resp = client.post("/abdm/consent/notify", content=body, headers=_headers(sig, key_id, payload["requestId"], old_ts))
    assert resp.status_code == 401


def test_missing_signature_header_returns_401(client):
    payload = _payload()
    timestamp = payload["timestamp"]
    headers = _headers("", "", payload["requestId"], timestamp)
    headers.pop("X-Signature")
    body = _json_bytes(payload)
    resp = client.post("/abdm/consent/notify", content=body, headers=headers)
    assert resp.status_code == 401
