from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.models.tenant_key import TenantKey
from app.security.emergency_enforcement_service import (
    enforce_emergency_decrypt,
    insert_decrypt_event,
)

class KMSClient(Protocol):
    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypts plaintext with master key; returns ciphertext bytes."""
        ...

    def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypts ciphertext with master key; returns plaintext bytes."""
        ...


class KMSNotConfiguredError(RuntimeError):
    pass


class NullKMSClient:
    def encrypt(self, plaintext: bytes) -> bytes:  # noqa: D401
        raise KMSNotConfiguredError("KMS client not configured")

    def decrypt(self, ciphertext: bytes) -> bytes:  # noqa: D401
        raise KMSNotConfiguredError("KMS client not configured")


@dataclass(frozen=True)
class CiphertextEnvelope:
    v: int
    alg: str
    kid: str
    nonce: str
    ct: str

    def to_dict(self) -> dict:
        return {
            "v": self.v,
            "alg": self.alg,
            "kid": self.kid,
            "nonce": self.nonce,
            "ct": self.ct,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CiphertextEnvelope":
        return cls(
            v=int(data["v"]),
            alg=str(data["alg"]),
            kid=str(data["kid"]),
            nonce=str(data["nonce"]),
            ct=str(data["ct"]),
        )


class EncryptionService:
    """
    Envelope encryption using per-tenant DEK wrapped by a master key in KMS.

    - generate_data_key(): returns (plaintext_dek, encrypted_dek)
    - encrypt(): uses decrypted DEK + tenant_id as AAD
    - decrypt(): uses decrypted DEK + tenant_id as AAD
    """

    def __init__(self, kms_client: KMSClient | None = None) -> None:
        self.kms = kms_client or NullKMSClient()

    def generate_data_key(self) -> tuple[bytes, bytes]:
        dek = os.urandom(32)
        encrypted_dek = self.kms.encrypt(dek)
        return dek, encrypted_dek

    def _build_kid(self, tenant_id: UUID, key_version: str) -> str:
        return f"{tenant_id}:{key_version}"

    def _parse_kid(self, kid: str) -> tuple[UUID, str]:
        try:
            tenant_part, key_version = kid.split(":", 1)
            return UUID(tenant_part), key_version
        except Exception as exc:  # noqa: BLE001
            raise ValueError("INVALID_KID_FORMAT") from exc

    def ensure_active_tenant_key(self, db, tenant_id: UUID) -> TenantKey:
        key = (
            db.query(TenantKey)
            .filter(TenantKey.tenant_id == tenant_id, TenantKey.is_active.is_(True))
            .order_by(TenantKey.created_at.desc())
            .first()
        )
        if key:
            return key

        existing = db.query(TenantKey).filter(TenantKey.tenant_id == tenant_id).all()
        if existing:
            max_version = max(int(k.key_version or "0") for k in existing)
            next_version = str(max_version + 1)
        else:
            next_version = "1"

        dek, encrypted_dek = self.generate_data_key()
        key = TenantKey(
            tenant_id=tenant_id,
            encrypted_dek=base64.b64encode(encrypted_dek).decode("utf-8"),
            key_version=next_version,
            is_active=True,
        )
        db.add(key)
        db.flush()
        return key

    def get_tenant_key_by_version(self, db, tenant_id: UUID, key_version: str) -> TenantKey:
        key = (
            db.query(TenantKey)
            .filter(TenantKey.tenant_id == tenant_id, TenantKey.key_version == key_version)
            .first()
        )
        if not key:
            raise ValueError("KEY_VERSION_NOT_FOUND")
        return key

    def encrypt(
        self,
        plaintext: bytes,
        encrypted_dek: bytes,
        tenant_id: UUID,
        key_version: str,
    ) -> CiphertextEnvelope:
        if not key_version:
            raise ValueError("KEY_VERSION_REQUIRED")
        dek = bytearray(self.kms.decrypt(encrypted_dek))
        try:
            aesgcm = AESGCM(bytes(dek))
            nonce = os.urandom(12)
            aad = str(tenant_id).encode("utf-8")
            ciphertext = aesgcm.encrypt(nonce, plaintext, aad)
            return CiphertextEnvelope(
                v=1,
                alg="AES-256-GCM",
                kid=self._build_kid(tenant_id, key_version),
                nonce=base64.b64encode(nonce).decode("utf-8"),
                ct=base64.b64encode(ciphertext).decode("utf-8"),
            )
        finally:
            for i in range(len(dek)):
                dek[i] = 0

    def encrypt_for_tenant(self, db, tenant_id: UUID, plaintext: bytes) -> dict:
        key = self.ensure_active_tenant_key(db, tenant_id)
        encrypted_dek = base64.b64decode(key.encrypted_dek)
        envelope = self.encrypt(plaintext, encrypted_dek, tenant_id, key.key_version or "1")
        return envelope.to_dict()

    def decrypt(
        self,
        envelope: dict,
        encrypted_dek: bytes,
        tenant_id: UUID,
    ) -> bytes:
        env = CiphertextEnvelope.from_dict(envelope)
        if env.v != 1 or env.alg != "AES-256-GCM":
            raise ValueError("UNSUPPORTED_ENCRYPTION_ENVELOPE")

        env_tenant_id, _version = self._parse_kid(env.kid)
        if env_tenant_id != tenant_id:
            raise ValueError("TENANT_MISMATCH")

        dek = bytearray(self.kms.decrypt(encrypted_dek))
        try:
            aesgcm = AESGCM(bytes(dek))
            nonce = base64.b64decode(env.nonce)
            ciphertext = base64.b64decode(env.ct)
            aad = str(tenant_id).encode("utf-8")
            return aesgcm.decrypt(nonce, ciphertext, aad)
        finally:
            for i in range(len(dek)):
                dek[i] = 0

    def decrypt_for_tenant(
        self,
        db,
        tenant_id: UUID,
        envelope: dict,
        *,
        request=None,
        emergency_session=None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> bytes:
        env = CiphertextEnvelope.from_dict(envelope)
        _, key_version = self._parse_kid(env.kid)
        key = self.get_tenant_key_by_version(db, tenant_id, key_version)
        encrypted_dek = base64.b64decode(key.encrypted_dek)
        session = emergency_session
        if session is None and request is not None:
            state = getattr(request, "state", None)
            session = getattr(state, "emergency_session", None) if state else None
        if session is not None:
            enforce_emergency_decrypt(db=db, session_id=session.id)
            effective_ip = ip or (request.client.host if request and request.client else "unknown")
            effective_ua = user_agent or (request.headers.get("user-agent", "unknown") if request else "unknown")
            insert_decrypt_event(
                db,
                session_id=session.id,
                tenant_id=session.tenant_id,
                super_admin_id=session.super_admin_id,
                ip=effective_ip,
                user_agent=effective_ua,
            )
        return self.decrypt(env.to_dict(), encrypted_dek, tenant_id)
