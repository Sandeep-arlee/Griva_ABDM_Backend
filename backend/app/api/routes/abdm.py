from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.audit_log import AuditLog
from app.models.consent import Consent, ConsentStatus
from app.models.consent_event import ConsentEvent
from app.schemas.consent import ConsentNotifyRequest, ConsentNotifyResponse
from app.schemas.health_info import HealthInformationRequest, HealthInformationResponse

router = APIRouter(prefix="/abdm", tags=["abdm"])


# -----------------------------
# Time helpers
# -----------------------------
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_utc_timestamp(raw: str) -> datetime:
    if not raw.endswith("Z"):
        raise ValueError("Timestamp must be UTC with Z suffix")
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise ValueError("Timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _ensure_utc(dt: datetime, label: str) -> None:
    if dt.tzinfo is None or dt.utcoffset() != timezone.utc.utcoffset(dt):
        raise HTTPException(status_code=400, detail=f"{label}_TIMESTAMP_NOT_UTC")


# -----------------------------
# Artefact helpers
# -----------------------------
def _parse_dates(artefact) -> tuple[datetime, datetime]:
    if artefact and artefact.permission and artefact.permission.dateRange:
        return artefact.permission.dateRange.from_, artefact.permission.dateRange.to
    now = _now_utc()
    return now, now


def _safe_entity_id(entity, fallback: str) -> str:
    return entity.id if entity and entity.id else fallback


def _validate_artefact_id(artefact_id: str) -> None:
    if not isinstance(artefact_id, str) or not artefact_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INVALID_CONSENT_ARTEFACT_ID",
        )


# -----------------------------
# Auditing
# -----------------------------
def _audit(
    db: Session,
    event_type: str,
    headers: dict,
    status_code: int,
    consent_id: str | None = None,
    meta: dict | None = None,
) -> None:
    audit = AuditLog(
        event_type=event_type,
        request_id=headers.get("request_id"),
        hip_id=headers.get("hip_id"),
        hiu_id=headers.get("hiu_id"),
        cm_id=headers.get("cm_id"),
        consent_id=consent_id,
        status_code=status_code,
        meta=meta or {},
    )
    db.add(audit)


# -----------------------------
# Header validation
# -----------------------------
def _require_abdm_headers(
    x_hip_id: str | None = Header(default=None, alias="X-HIP-ID"),
    x_hiu_id: str | None = Header(default=None, alias="X-HIU-ID"),
    x_cm_id: str | None = Header(default=None, alias="X-CM-ID"),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    x_timestamp: str | None = Header(default=None, alias="X-Timestamp"),
    db: Session = Depends(get_db),
) -> dict:
    if not all([x_hip_id, x_hiu_id, x_cm_id, x_request_id, x_timestamp]):
        _audit(
            db,
            event_type="ABDM_HEADER_VALIDATION",
            headers={
                "hip_id": x_hip_id,
                "hiu_id": x_hiu_id,
                "cm_id": x_cm_id,
                "request_id": x_request_id,
                "timestamp": x_timestamp,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
            meta={"error": "MISSING_REQUIRED_HEADERS"},
        )
        db.commit()
        raise HTTPException(status_code=400, detail="MISSING_REQUIRED_HEADERS")

    try:
        _parse_utc_timestamp(x_timestamp)
    except ValueError as exc:
        _audit(
            db,
            event_type="ABDM_HEADER_VALIDATION",
            headers={
                "hip_id": x_hip_id,
                "hiu_id": x_hiu_id,
                "cm_id": x_cm_id,
                "request_id": x_request_id,
                "timestamp": x_timestamp,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
            meta={"error": str(exc)},
        )
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "hip_id": x_hip_id,
        "hiu_id": x_hiu_id,
        "cm_id": x_cm_id,
        "request_id": x_request_id,
        "timestamp": x_timestamp,
    }


# -----------------------------
# Consent Notify
# -----------------------------
@router.post(
    "/consent/notify",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ConsentNotifyResponse,
)
def consent_notify(
    payload: ConsentNotifyRequest,
    headers: dict = Depends(_require_abdm_headers),
    db: Session = Depends(get_db),
) -> ConsentNotifyResponse:
    if headers["request_id"] != payload.requestId:
        _audit(
            db,
            event_type="ABDM_CONSENT_NOTIFY",
            headers=headers,
            status_code=400,
            meta={"error": "REQUEST_ID_MISMATCH"},
        )
        db.commit()
        raise HTTPException(status_code=400, detail="REQUEST_ID_MISMATCH")

    _ensure_utc(payload.timestamp, "REQUEST")

    if payload.notification.status not in ConsentStatus._value2member_map_:
        _audit(
            db,
            event_type="ABDM_CONSENT_NOTIFY",
            headers=headers,
            status_code=400,
            meta={"error": "INVALID_CONSENT_STATUS"},
        )
        db.commit()
        raise HTTPException(status_code=400, detail="INVALID_CONSENT_STATUS")

    count = 0

    for artefact_ref in payload.notification.consentArtefacts:
        if not artefact_ref.artefact or not artefact_ref.artefact.id:
            _audit(
                db,
                event_type="ABDM_CONSENT_NOTIFY",
                headers=headers,
                status_code=400,
                meta={"error": "INVALID_CONSENT_ARTEFACT"},
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_CONSENT_ARTEFACT",
            )

        consent_id = artefact_ref.artefact.id
        artefact = artefact_ref.artefact

        valid_from, valid_to = _parse_dates(artefact)
        if valid_from > valid_to:
            _audit(
                db,
                event_type="ABDM_CONSENT_NOTIFY",
                headers=headers,
                status_code=400,
                consent_id=consent_id,
                meta={"error": "INVALID_CONSENT_DATE_RANGE"},
            )
            db.commit()
            raise HTTPException(status_code=400, detail="INVALID_CONSENT_DATE_RANGE")

        upsert_stmt = (
            insert(Consent)
            .values(
                abdm_consent_id=consent_id,
                patient_id=_safe_entity_id(artefact.patient if artefact else None, "UNKNOWN"),
                hiu_id=_safe_entity_id(artefact.hiu if artefact else None, "UNKNOWN"),
                hip_id=_safe_entity_id(artefact.hip if artefact else None, "UNKNOWN"),
                status=ConsentStatus(payload.notification.status),
                valid_from=valid_from,
                valid_to=valid_to,
                raw_payload=payload.model_dump(mode="json", by_alias=True),
            )
            .on_conflict_do_update(
                index_elements=[Consent.abdm_consent_id],
                set_={
                    "status": ConsentStatus(payload.notification.status),
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                    "raw_payload": payload.model_dump(mode="json", by_alias=True),
                },
            )
        )
        try:
            db.execute(upsert_stmt)
        except IntegrityError:
            db.rollback()
            db.execute(upsert_stmt)

        consent = db.query(Consent).filter(Consent.abdm_consent_id == consent_id).one()

        db.add(
            ConsentEvent(
                consent=consent,
                event_type=ConsentStatus(payload.notification.status),
                event_payload=payload.model_dump(mode="json", by_alias=True),
            )
        )

        count += 1


    _audit(
        db,
        event_type="ABDM_CONSENT_NOTIFY",
        headers=headers,
        status_code=202,
        meta={"consents": count, "status": payload.notification.status},
    )
    db.commit()
    return ConsentNotifyResponse(received=count)


# -----------------------------
# Health Information Request
# -----------------------------
@router.post(
    "/health-information/request",
    response_model=HealthInformationResponse,
)
def health_information_request(
    payload: HealthInformationRequest,
    headers: dict = Depends(_require_abdm_headers),
    db: Session = Depends(get_db),
) -> HealthInformationResponse:
    if headers["request_id"] != payload.hiRequest.requestId:
        _audit(
            db,
            event_type="ABDM_HI_REQUEST",
            headers=headers,
            status_code=400,
            meta={"error": "REQUEST_ID_MISMATCH"},
        )
        db.commit()
        raise HTTPException(status_code=400, detail="REQUEST_ID_MISMATCH")

    _ensure_utc(payload.hiRequest.timestamp, "REQUEST")

    consent = db.query(Consent).filter(Consent.abdm_consent_id == payload.consentId).first()

    if consent is None:
        _audit(
            db,
            event_type="ABDM_HI_REQUEST",
            headers=headers,
            status_code=404,
            consent_id=payload.consentId,
            meta={"error": "CONSENT_NOT_FOUND"},
        )
        db.commit()
        raise HTTPException(status_code=404, detail="CONSENT_NOT_FOUND")

    if consent.status in {
        ConsentStatus.REQUESTED,
        ConsentStatus.REVOKED,
        ConsentStatus.DENIED,
    }:
        error = f"CONSENT_{consent.status.name}"
        _audit(
            db,
            event_type="ABDM_HI_REQUEST",
            headers=headers,
            status_code=403,
            consent_id=payload.consentId,
            meta={"error": error},
        )
        db.commit()
        raise HTTPException(status_code=403, detail=error)

    now = _now_utc()
    if consent.status == ConsentStatus.EXPIRED or not (
        consent.valid_from <= now <= consent.valid_to
    ):
        _audit(
            db,
            event_type="ABDM_HI_REQUEST",
            headers=headers,
            status_code=403,
            consent_id=payload.consentId,
            meta={"error": "CONSENT_EXPIRED"},
        )
        db.commit()
        raise HTTPException(status_code=403, detail="CONSENT_EXPIRED")

    dr = payload.hiRequest.dateRange
    if dr.from_ > dr.to:
        _audit(
            db,
            event_type="ABDM_HI_REQUEST",
            headers=headers,
            status_code=400,
            consent_id=payload.consentId,
            meta={"error": "INVALID_HI_DATE_RANGE"},
        )
        db.commit()
        raise HTTPException(status_code=400, detail="INVALID_HI_DATE_RANGE")

    if "ImagingStudy" not in payload.hiRequest.hiTypes:
        _audit(
            db,
            event_type="ABDM_HI_REQUEST",
            headers=headers,
            status_code=400,
            consent_id=payload.consentId,
            meta={"error": "UNSUPPORTED_HI_TYPE"},
        )
        db.commit()
        raise HTTPException(status_code=400, detail="UNSUPPORTED_HI_TYPE")

    if dr.from_ < consent.valid_from or dr.to > consent.valid_to:
        _audit(
            db,
            event_type="ABDM_HI_REQUEST",
            headers=headers,
            status_code=400,
            consent_id=payload.consentId,
            meta={"error": "DATE_RANGE_OUTSIDE_CONSENT"},
        )
        db.commit()
        raise HTTPException(status_code=400, detail="DATE_RANGE_OUTSIDE_CONSENT")

    _audit(
        db,
        event_type="ABDM_HI_REQUEST",
        headers=headers,
        status_code=200,
        consent_id=payload.consentId,
        meta={"status": "OK"},
    )
    db.commit()

    return HealthInformationResponse(
        transactionId=payload.transactionId,
        entries=[
            {
                "content": "mock-encrypted-colposcope-image",
                "media": "image/jpeg",
            }
        ],
    )
