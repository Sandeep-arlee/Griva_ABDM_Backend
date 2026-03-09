from __future__ import annotations

import base64
import hashlib
import os
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import text
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.encryption_service import EncryptionService
from app.models.patient import Patient
from app.models.patient_abha_link import PatientAbhaLink

_KMS_AAD = b"griva:tenant:kms"


class TenantMasterKeyNotConfigured(RuntimeError):
    pass


class LocalKMSClient:
    def __init__(self, master_key: bytes) -> None:
        if len(master_key) != 32:
            raise ValueError("TENANT_MASTER_KEY_INVALID_LENGTH")
        self._master_key = master_key

    def encrypt(self, plaintext: bytes) -> bytes:
        nonce = os.urandom(12)
        aesgcm = AESGCM(self._master_key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, _KMS_AAD)
        return nonce + ciphertext

    def decrypt(self, ciphertext: bytes) -> bytes:
        if len(ciphertext) < 13:
            raise ValueError("INVALID_KMS_CIPHERTEXT")
        nonce = ciphertext[:12]
        ct = ciphertext[12:]
        aesgcm = AESGCM(self._master_key)
        return aesgcm.decrypt(nonce, ct, _KMS_AAD)


def _get_encryption_service() -> EncryptionService:
    if not settings.tenant_master_key_b64:
        raise TenantMasterKeyNotConfigured("Tenant master key not configured")
    master_key = base64.b64decode(settings.tenant_master_key_b64)
    return EncryptionService(kms_client=LocalKMSClient(master_key))


def _ensure_tenant_context(db: Session, tenant_id: UUID) -> bool:
    current = db.info.get("tenant_id")
    if current and str(current) != str(tenant_id):
        raise ValueError("TENANT_CONTEXT_MISMATCH")
    if not current:
        db.info["tenant_id"] = tenant_id
        return True
    return False


def normalize_abha(value: str) -> str:
    return value.strip().lower()


def _hash_abha(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def encrypt_abha(db: Session, tenant_id: UUID, value: str) -> dict:
    service = _get_encryption_service()
    envelope = service.encrypt_for_tenant(db, tenant_id, value.encode("utf-8"))
    return envelope


def decrypt_abha(db: Session, tenant_id: UUID, envelope: dict) -> str:
    service = _get_encryption_service()
    plaintext = service.decrypt_for_tenant(db, tenant_id, envelope)
    return plaintext.decode("utf-8")


def link_abha_to_patient(
    db: Session,
    tenant_id: UUID,
    patient_id: UUID,
    abha_address: str | None,
    abha_number: str | None,
) -> PatientAbhaLink:
    row = db.execute(
        text("SELECT id FROM patients WHERE id = :pid AND tenant_id = :tid"),
        {"pid": str(patient_id), "tid": str(tenant_id)},
    ).first()
    if not row:
        raise ValueError("PATIENT_NOT_FOUND")

    abha_value = abha_address or abha_number
    if not abha_value:
        raise ValueError("ABHA_REQUIRED")

    normalized = normalize_abha(abha_value)
    abha_hash = _hash_abha(normalized)

    abha_address_enc = encrypt_abha(db, tenant_id, abha_address) if abha_address else None
    abha_number_enc = encrypt_abha(db, tenant_id, abha_number) if abha_number else None

    link = PatientAbhaLink(
        tenant_id=tenant_id,
        patient_id=patient_id,
        abha_address_enc=abha_address_enc,
        abha_number_enc=abha_number_enc,
        abha_hash=abha_hash,
        link_status="VERIFIED",
        verified_at=func.now(),
    )
    db.add(link)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("ABHA_ALREADY_LINKED") from exc

    return link


def get_patient_by_abha(db: Session, tenant_id: UUID, abha: str) -> Patient | None:
    normalized = normalize_abha(abha)
    abha_hash = _hash_abha(normalized)
    reset_tenant = _ensure_tenant_context(db, tenant_id)
    try:
        patient = (
            db.query(Patient)
            .join(PatientAbhaLink, PatientAbhaLink.patient_id == Patient.id)
            .filter(PatientAbhaLink.tenant_id == tenant_id)
            .filter(PatientAbhaLink.abha_hash == abha_hash)
            .first()
        )
        return patient
    finally:
        if reset_tenant:
            db.info.pop("tenant_id", None)
