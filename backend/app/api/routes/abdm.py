from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.audit_log import AuditLog
from app.models.consent import Consent, ConsentStatus
from app.models.consent_event import ConsentEvent
from app.models.health_information_event import HealthInformationEvent
from app.models.health_information_request import (
    HealthInformationRequest as HIRequest,
    HealthInformationRequestStatus,
)
from app.models.medical_record import MedicalRecord
from app.db.session import SessionLocal
from app.schemas.consent import ConsentArtefact, ConsentNotifyRequest, ConsentNotifyResponse
from app.schemas.health_info import HealthInformationRequest, HealthInformationRequestAccepted

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


def _extract_allowed_hi_types(consent: Consent) -> set[str] | None:
    payload = consent.raw_payload or {}
    notification = payload.get("notification", {})
    artefacts = notification.get("consentArtefacts", [])
    for item in artefacts:
        artefact = item.get("artefact") if isinstance(item, dict) else None
        if not isinstance(artefact, dict):
            artefact = item if isinstance(item, dict) else {}
        if artefact.get("id") == consent.abdm_consent_id:
            hi_types = artefact.get("hiTypes")
            if isinstance(hi_types, list):
                return {str(value) for value in hi_types}
    return None


def _latest_consent_status(db: Session, consent_id: str) -> ConsentStatus | None:
    event = (
        db.query(ConsentEvent)
        .filter(ConsentEvent.consent_id == consent_id)
        .order_by(ConsentEvent.timestamp.desc(), ConsentEvent.id.desc())
        .first()
    )
    return event.event_type if event else None


def _build_transfer_payload(hi_request: HIRequest, consent: Consent, records: list[MedicalRecord]) -> dict:
    return {
        "requestId": hi_request.request_id,
        "timestamp": _now_utc().isoformat().replace("+00:00", "Z"),
        "consentId": consent.abdm_consent_id,
        "hipId": hi_request.hip_id,
        "hiuId": hi_request.hiu_id,
        "entries": [
            {
                "contentRef": {"uri": record.uri},
                "media": "image/jpeg",
            }
            for record in records
        ],
    }


def _dispatch_transfer(request_id: str) -> None:
    db = SessionLocal()
    hi_request = None
    try:
        hi_request = db.query(HIRequest).filter(HIRequest.request_id == request_id).first()
        if not hi_request:
            return

        consent = db.query(Consent).filter(Consent.id == hi_request.consent_id).first()
        if not consent:
            hi_request.status = HealthInformationRequestStatus.FAILED
            db.add(
                HealthInformationEvent(
                    health_information_request_id=hi_request.id,
                    event_type="TRANSFER_FAILED",
                    event_payload={"error": "CONSENT_NOT_FOUND"},
                )
            )
            db.commit()
            return

        hi_request.status = HealthInformationRequestStatus.PROCESSING
        db.add(
            HealthInformationEvent(
                health_information_request_id=hi_request.id,
                event_type="PROCESSING",
                event_payload={},
            )
        )
        db.flush()

        date_range = hi_request.date_range or {}
        from_raw = date_range.get("from")
        to_raw = date_range.get("to")
        if not from_raw or not to_raw:
            raise ValueError("DATE_RANGE_MISSING")

        start = datetime.fromisoformat(str(from_raw).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(to_raw).replace("Z", "+00:00"))

        records = (
            db.query(MedicalRecord)
            .filter(MedicalRecord.patient_id == consent.patient_id)
            .filter(MedicalRecord.created_at >= start)
            .filter(MedicalRecord.created_at <= end)
            .all()
        )

        payload = _build_transfer_payload(hi_request, consent, records)
        db.add(
            HealthInformationEvent(
                health_information_request_id=hi_request.id,
                event_type="TRANSFER_DISPATCHED",
                event_payload=payload,
            )
        )
        hi_request.status = HealthInformationRequestStatus.COMPLETED
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        if hi_request:
            hi_request.status = HealthInformationRequestStatus.FAILED
            db.add(
                HealthInformationEvent(
                    health_information_request_id=hi_request.id,
                    event_type="TRANSFER_FAILED",
                    event_payload={"error": str(exc)},
                )
            )
            db.commit()
    finally:
        db.close()


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

    for artefact_item in payload.notification.consentArtefacts:
        # ABDM payloads may supply artefacts directly or wrapped under {"id","artefact"}.
        if isinstance(artefact_item, ConsentArtefact):
            artefact = artefact_item
        else:
            if not artefact_item.artefact or not artefact_item.artefact.id:
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
            artefact = artefact_item.artefact

        if not artefact.id:
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

        if artefact.hip.id != headers["hip_id"] or artefact.hiu.id != headers["hiu_id"]:
            _audit(
                db,
                event_type="ABDM_CONSENT_NOTIFY",
                headers=headers,
                status_code=400,
                meta={"error": "HIP_HIU_MISMATCH"},
            )
            db.commit()
            raise HTTPException(status_code=400, detail="HIP_HIU_MISMATCH")

        consent_id = artefact.id

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

        insert_stmt = (
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
            .on_conflict_do_nothing(index_elements=[Consent.abdm_consent_id])
        )
        try:
            db.execute(insert_stmt)
        except IntegrityError:
            db.rollback()
            db.execute(insert_stmt)

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
    response_model=HealthInformationRequestAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def health_information_request(
    payload: HealthInformationRequest,
    background_tasks: BackgroundTasks,
    headers: dict = Depends(_require_abdm_headers),
    db: Session = Depends(get_db),
) -> HealthInformationRequestAccepted:
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

    existing = db.query(HIRequest).filter(HIRequest.request_id == payload.hiRequest.requestId).first()
    if existing:
        db.add(
            HealthInformationEvent(
                health_information_request_id=existing.id,
                event_type="DUPLICATE_REQUEST",
                event_payload={"request_id": payload.hiRequest.requestId},
            )
        )
        _audit(
            db,
            event_type="ABDM_HI_REQUEST",
            headers=headers,
            status_code=202,
            consent_id=payload.consentId,
            meta={"status": "DUPLICATE"},
        )
        db.commit()
        return HealthInformationRequestAccepted(requestId=payload.hiRequest.requestId)

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

    latest_status = _latest_consent_status(db, consent.id)
    if latest_status != ConsentStatus.GRANTED:
        error = "CONSENT_NOT_GRANTED"
        _audit(
            db,
            event_type="ABDM_HI_REQUEST",
            headers=headers,
            status_code=409,
            consent_id=payload.consentId,
            meta={"error": error},
        )
        db.commit()
        raise HTTPException(status_code=409, detail=error)

    now = _now_utc()
    if latest_status == ConsentStatus.EXPIRED or not (
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
        raise HTTPException(status_code=409, detail="CONSENT_EXPIRED")

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

    allowed_types = _extract_allowed_hi_types(consent)
    if not allowed_types:
        _audit(
            db,
            event_type="ABDM_HI_REQUEST",
            headers=headers,
            status_code=422,
            consent_id=payload.consentId,
            meta={"error": "CONSENT_SCOPE_UNKNOWN"},
        )
        db.commit()
        raise HTTPException(status_code=422, detail="CONSENT_SCOPE_UNKNOWN")

    requested_types = set(payload.hiRequest.hiTypes)
    if not requested_types.issubset(allowed_types):
        _audit(
            db,
            event_type="ABDM_HI_REQUEST",
            headers=headers,
            status_code=422,
            consent_id=payload.consentId,
            meta={"error": "HI_TYPE_OUTSIDE_CONSENT"},
        )
        db.commit()
        raise HTTPException(status_code=422, detail="HI_TYPE_OUTSIDE_CONSENT")

    if dr.from_ < consent.valid_from or dr.to > consent.valid_to:
        _audit(
            db,
            event_type="ABDM_HI_REQUEST",
            headers=headers,
            status_code=422,
            consent_id=payload.consentId,
            meta={"error": "DATE_RANGE_OUTSIDE_CONSENT"},
        )
        db.commit()
        raise HTTPException(status_code=422, detail="DATE_RANGE_OUTSIDE_CONSENT")

    hi_request = HIRequest(
        request_id=payload.hiRequest.requestId,
        consent_id=consent.id,
        hip_id=headers["hip_id"],
        hiu_id=headers["hiu_id"],
        status=HealthInformationRequestStatus.REQUESTED,
        date_range={
            "from": dr.from_.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "to": dr.to.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
    )
    db.add(hi_request)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.query(HIRequest).filter(HIRequest.request_id == payload.hiRequest.requestId).first()
        if existing:
            db.add(
                HealthInformationEvent(
                    health_information_request_id=existing.id,
                    event_type="DUPLICATE_REQUEST",
                    event_payload={"request_id": payload.hiRequest.requestId},
                )
            )
            _audit(
                db,
                event_type="ABDM_HI_REQUEST",
                headers=headers,
                status_code=202,
                consent_id=payload.consentId,
                meta={"status": "DUPLICATE"},
            )
            db.commit()
            return HealthInformationRequestAccepted(requestId=payload.hiRequest.requestId)
        raise

    db.add(
        HealthInformationEvent(
            health_information_request_id=hi_request.id,
            event_type="REQUESTED",
            event_payload={"request_id": payload.hiRequest.requestId},
        )
    )

    _audit(
        db,
        event_type="ABDM_HI_REQUEST",
        headers=headers,
        status_code=202,
        consent_id=payload.consentId,
        meta={"status": "ACCEPTED"},
    )
    db.commit()

    background_tasks.add_task(_dispatch_transfer, hi_request.request_id)
    return HealthInformationRequestAccepted(requestId=payload.hiRequest.requestId)
