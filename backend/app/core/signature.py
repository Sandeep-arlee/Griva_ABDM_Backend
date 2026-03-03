from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.exceptions import InvalidSignature

from app.models.trusted_key import TrustedKey


def hash_body(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def canonicalize_request(
    method: str,
    path: str,
    request_id: str,
    timestamp: str,
    body_hash: str,
) -> bytes:
    canonical = "\n".join([method.upper(), path, request_id, timestamp, body_hash])
    return canonical.encode("utf-8")


def canonicalize_response(
    status_code: int,
    path: str,
    request_id: str,
    timestamp: str,
    body_hash: str,
) -> bytes:
    canonical = "\n".join([str(status_code), path, request_id, timestamp, body_hash])
    return canonical.encode("utf-8")


def load_public_key(key_id: str, db: Optional[Session] = None) -> Optional[EllipticCurvePublicKey]:
    if db is None:
        raise ValueError("Database session is required to load a public key.")
    key = (
        db.query(TrustedKey)
        .filter(TrustedKey.key_id == key_id, TrustedKey.is_active.is_(True))
        .first()
    )
    if not key:
        return None
    return serialization.load_pem_public_key(key.public_key.encode("utf-8"))


def verify_signature(signature_b64: str, public_key: EllipticCurvePublicKey, data: bytes) -> bool:
    try:
        signature = base64.b64decode(signature_b64)
        public_key.verify(signature, data, ec.ECDSA(hashes.SHA256()))
        return True
    except (ValueError, InvalidSignature):
        return False


def sign_response(private_key_pem: str, data: bytes) -> str:
    private_key = serialization.load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
    signature = private_key.sign(data, ec.ECDSA(hashes.SHA256()))
    return base64.b64encode(signature).decode("utf-8")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
