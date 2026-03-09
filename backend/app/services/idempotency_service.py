from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.models.idempotency_key import IdempotencyKey


def _response_hash(response: Any) -> str:
    if hasattr(response, "model_dump"):
        payload = response.model_dump(mode="json")
    elif isinstance(response, dict):
        payload = response
    else:
        payload = {"value": response}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def check_request(db: Session, tenant_id: UUID, request_id: str, endpoint: str) -> IdempotencyKey | None:
    return (
        db.query(IdempotencyKey)
        .filter(
            IdempotencyKey.request_id == request_id,
            IdempotencyKey.endpoint == endpoint,
            IdempotencyKey.tenant_id == tenant_id,
        )
        .first()
    )


def store_response(
    db: Session,
    tenant_id: UUID,
    request_id: str,
    endpoint: str,
    response: Any,
    status_code: int,
) -> None:
    stmt = (
        insert(IdempotencyKey)
        .values(
            request_id=request_id,
            endpoint=endpoint,
            response_hash=_response_hash(response),
            status_code=status_code,
            tenant_id=tenant_id,
        )
        .on_conflict_do_nothing(index_elements=[IdempotencyKey.request_id])
    )
    db.execute(stmt)
