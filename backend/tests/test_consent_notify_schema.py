import pytest
from pydantic import ValidationError

from app.schemas.consent import ConsentNotifyRequest


def _artefact() -> dict:
    return {
        "id": "CONSENT-001",
        "patient": {"id": "abha-123"},
        "hiu": {"id": "HIU_TEST"},
        "hip": {"id": "HIP_TEST"},
        "purpose": {"code": "CAREMGT", "refUri": "https://abdm.gov.in/purpose"},
        "hiTypes": ["OPConsultation"],
        "permission": {
            "accessMode": "VIEW",
            "dateRange": {"from": "2026-01-01T00:00:00Z", "to": "2026-12-31T23:59:59Z"},
            "frequency": {"unit": "HOUR", "value": 1, "repeats": 1},
            "dataEraseAt": "2027-01-01T00:00:00Z",
        },
    }


def _base_payload(consent_artefacts: list[dict]) -> dict:
    return {
        "requestId": "req-001",
        "timestamp": "2026-02-04T10:00:00Z",
        "notification": {
            "consentRequestId": "CR-123",
            "status": "GRANTED",
            "consentArtefacts": consent_artefacts,
        },
    }


def test_valid_direct_artefact_passes() -> None:
    payload = _base_payload([_artefact()])
    ConsentNotifyRequest.model_validate(payload)


def test_valid_wrapped_artefact_passes() -> None:
    payload = _base_payload([{"id": "REF-001", "artefact": _artefact()}])
    ConsentNotifyRequest.model_validate(payload)


def test_missing_required_fields_fail() -> None:
    artefact = _artefact()
    artefact["permission"].pop("frequency")
    payload = _base_payload([artefact])
    with pytest.raises(ValidationError):
        ConsentNotifyRequest.model_validate(payload)


def test_malformed_wrapper_fails() -> None:
    payload = _base_payload([{"id": "REF-001"}])
    with pytest.raises(ValidationError):
        ConsentNotifyRequest.model_validate(payload)
