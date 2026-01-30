# ABDM Colposcopy Backend + Frontend (Sandbox-Oriented)

This repo provides a production-oriented, ABDM Phase-1 / Sandbox-aligned HIP/HIU service for colposcopy datasets with consent enforcement, audit logs, and a minimal dashboard UI.

## Stack
- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL
- Frontend: React (Vite), TypeScript
- Security: JWT auth, role-based access (ADMIN, DOCTOR, SUPERADMIN)

## Backend setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Apply migrations
alembic upgrade head

# Run API
uvicorn app.main:app --reload
```

### Seed admin user
Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `.env`. The user is created at startup if missing.

## Frontend setup
```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE` in your shell or `.env` if your API runs elsewhere:
```bash
export VITE_API_BASE=http://localhost:8000
```

## ABDM consent notification
`POST /abdm/consent/notify`

The payload matches ABDM consent notification structure. For sandbox testing you can include the full consent artefact inside each `consentArtefacts[].artefact`.

```json
{
  "requestId": "req-uuid",
  "timestamp": "2025-02-01T10:00:00Z",
  "notification": {
    "consentRequestId": "consent-request-id",
    "status": "GRANTED",
    "consentArtefacts": [
      {
        "id": "consent-artefact-id",
        "artefact": {
          "id": "consent-artefact-id",
          "patient": { "id": "abha@abdm" },
          "hiu": { "id": "GRIVA_HIU" },
          "hip": { "id": "GRIVA_HIP" },
          "purpose": { "text": "CARE_MANAGEMENT", "code": "CAREMGT" },
          "hiTypes": ["ImagingStudy"],
          "permission": {
            "accessMode": "VIEW",
            "dateRange": {
              "from": "2025-01-01T00:00:00Z",
              "to": "2025-12-31T23:59:59Z"
            }
          }
        }
      }
    ]
  }
}
```

Consent records are immutable except for status updates. Every notification creates a `consent_events` audit record.

## Health information request
`POST /abdm/health-information/request`

```json
{
  "transactionId": "txn-uuid",
  "consentId": "consent-artefact-id",
  "hiRequest": {
    "requestId": "req-uuid",
    "timestamp": "2025-02-01T10:00:00Z",
    "hiTypes": ["ImagingStudy"],
    "dateRange": {
      "from": "2025-01-01T00:00:00Z",
      "to": "2025-02-01T00:00:00Z"
    }
  }
}
```

Failure responses: `CONSENT_REVOKED`, `CONSENT_EXPIRED`, `CONSENT_DENIED`, `CONSENT_NOT_FOUND`.

## Internal clinical APIs
- `POST /api/records/upload`
- `GET /api/patients/{id}/records`

Both require JWT auth and support ADMIN/DOCTOR/SUPERADMIN roles.

## Notes for production hardening
- Replace `mock-encrypted-colposcope-image` with real encrypted payloads from object storage.
- Use dedicated audit storage (append-only) and SIEM integrations.
- Configure TLS termination and forward-proxy for ABDM sandbox endpoints.
- Add HSM-backed secrets, rotation, and strict CORS/CSRF policies.

## ABDM audit checklist
See `docs/abdm-audit-checklist.md` for a milestone-by-milestone review checklist with ✅/⚠️/❌ status.
