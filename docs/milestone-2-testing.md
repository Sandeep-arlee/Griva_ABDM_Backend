# Milestone-2 Health Information Exchange Testing

## Headers (required for all requests)
- X-Request-ID
- X-Timestamp (UTC, ISO-8601 with Z)
- X-HIP-ID
- X-HIU-ID
- X-CM-ID

## Valid request
```bash
curl -X POST http://localhost:8000/abdm/health-information/request \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: req-001" \
  -H "X-Timestamp: 2026-02-04T10:00:00Z" \
  -H "X-HIP-ID: GRIVA_HIP" \
  -H "X-HIU-ID: GRIVA_HIU" \
  -H "X-CM-ID: CM_001" \
  -d '{
    "transactionId": "txn-001",
    "consentId": "CONSENT-001",
    "hiRequest": {
      "requestId": "req-001",
      "timestamp": "2026-02-04T10:00:00Z",
      "hiTypes": ["ImagingStudy"],
      "dateRange": {
        "from": "2026-02-01T00:00:00Z",
        "to": "2026-02-04T00:00:00Z"
      }
    }
  }'
```
Expected: `202 Accepted` with `{ "status": "ACCEPTED", "requestId": "req-001" }`

## Duplicate request (same requestId)
Re-send the same payload. Expected: `202 Accepted` and a new `health_information_events` row with `DUPLICATE_REQUEST`.

## Invalid consent
Use an unknown `consentId`. Expected: `404 CONSENT_NOT_FOUND`.

## Consent not granted
Use a consent that is not GRANTED. Expected: `409 CONSENT_NOT_GRANTED`.

## Scope violation
Request a `hiTypes` value not present in the consent artefact. Expected: `422 HI_TYPE_OUTSIDE_CONSENT`.

## Date range violation
Use a date range outside the consent validity window. Expected: `422 DATE_RANGE_OUTSIDE_CONSENT`.
