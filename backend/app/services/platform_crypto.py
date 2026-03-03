from __future__ import annotations

import base64
import json
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings
from app.core.encryption_service import CiphertextEnvelope

_AAD = b"griva:platform:identity"


class PlatformKeyNotConfigured(RuntimeError):
    pass


def _load_platform_key() -> bytes:
    if not settings.platform_identity_key_b64:
        raise PlatformKeyNotConfigured("Platform identity key not configured")
    return base64.b64decode(settings.platform_identity_key_b64)


def encrypt_hpr_profile(profile: dict[str, Any]) -> dict:
    key = _load_platform_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    plaintext = json.dumps(profile, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext, _AAD)
    envelope = CiphertextEnvelope(
        v=1,
        alg="AES-256-GCM",
        kid=f"platform:{settings.platform_identity_key_id}",
        nonce=base64.b64encode(nonce).decode("utf-8"),
        ct=base64.b64encode(ciphertext).decode("utf-8"),
    )
    return envelope.to_dict()


def decrypt_hpr_profile(envelope: dict) -> dict[str, Any]:
    env = CiphertextEnvelope.from_dict(envelope)
    if env.v != 1 or env.alg != "AES-256-GCM":
        raise ValueError("UNSUPPORTED_ENVELOPE")
    key = _load_platform_key()
    aesgcm = AESGCM(key)
    nonce = base64.b64decode(env.nonce)
    ciphertext = base64.b64decode(env.ct)
    plaintext = aesgcm.decrypt(nonce, ciphertext, _AAD)
    return json.loads(plaintext.decode("utf-8"))
