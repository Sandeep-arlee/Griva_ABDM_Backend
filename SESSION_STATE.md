# SESSION_STATE

## Overview
- Purpose: Backend state + deployment/test handoff for Griva ABDM platform
- Project: Griva ABDM backend
- Date: 2026-02-20
- Owner: abel
- Primary branch/tag: milestone-3-security

## Environment
- OS: Ubuntu 24.04.4 LTS
- Python: 3.12.3 (backend/venv)
- Virtualenv: /home/abel/myprojects/abdm/backend/venv
- Node: v24.11.1
- Database: PostgreSQL 16.11 (local)
- Network constraints: local dev; localhost only

## Repos / Paths
- Backend path: /home/abel/myprojects/abdm/backend
- Frontend path: /home/abel/myprojects/abdm/frontend
- Docs path: /home/abel/myprojects/abdm/docs

## Backend Layout (key modules)
- app/main.py: FastAPI app + router registration
- app/api/routes:
  - abdm.py: ABDM HIP endpoints (consent notify, HI request)
  - auth.py: JWT login/refresh
  - consents.py: list consents
  - patients.py: patient read endpoints
  - records.py: medical record upload/read (internal consent enforced)
  - internal_consents.py: internal consent grant/revoke
- app/api/deps.py: DB session + auth deps + tenant enforcement + internal consent checks
- app/api/middleware.py: raw body capture + tenant header middleware
- app/core:
  - security.py: JWT auth
  - signature.py: M3 signing/verification
  - encryption_service.py: envelope encryption + tenant DEKs
  - config.py: settings
- app/db/session.py: tenant filtering + before_flush tenant_id assignment
- app/tenancy.py: tenant context (ContextVar)
- app/models: SQLAlchemy models (users, patients, consents, events, audit, M3 tables, tenancy, internal consent)
- app/schemas: Pydantic schemas for auth, consent, health info, internal consent
- alembic/versions: migrations (see below)
- tests: pytest suite (see below)

## Runtime Services
- FastAPI:
  - Host/port: not running
  - Command: ./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
  - PID: none
  - Logs: /tmp/uvicorn.log (if started)
- Postgres:
  - Host/port: /var/run/postgresql, 5432
  - DBs: griva, griva_test
  - User: griva

## Secrets & Keys (DO NOT COMMIT VALUES)
- JWT secret: set in backend/.env (dev value)
- ABDM key id: LOCAL_KEY
- ABDM private key location: backend/abdm_private_key.pem and backend/.env (ABDM_PRIVATE_KEY_PEM)
- KMS config: not configured (NullKMSClient)
- Tenant key storage: tenant_keys table

## Tenancy
- Strict tenant mode: true (STRICT_TENANT_MODE default)
- Tenant header: X-Tenant-ID (UUID)
- Tenant IDs used in tests: 00000000-0000-0000-0000-000000000001
- Tenant seeding: manual insert; tests create tenant row
- Tenant enforcement: fail-closed; missing/unknown tenant returns 400
- Tenant filtering: global SQLAlchemy loader criteria for tenant-scoped models

## Database State
- Primary DB URL: postgresql+psycopg://griva:griva123@localhost:5432/griva
- Test DB URL: postgresql+psycopg://griva:griva123@localhost:5432/griva_test
- Alembic head: aa12bc34de56 (latest migration file)
- Latest migration applied: unknown (alembic current fails; see Known Issues)
- Pending migrations: aa12bc34de56_add_internal_consent_engine (likely pending)

## Alembic Migrations (in order)
- 0001_init.py: initial schema
- 2a532a436406_add_audit_logs_table.py: audit_logs + patients
- 4b1c8a9b7f1b_add_health_information_tables.py: HI request/event tables
- 5d2c7b9c1e2f_add_trusted_keys_and_requests.py: trusted_keys, trusted_requests
- 8c2f3a5b9d01_add_tenants_and_tenant_ids.py: tenants + tenant_id columns
- 9f7c2d1e3b42_add_tenant_keys_table.py: tenant_keys for envelope encryption
- aa12bc34de56_add_internal_consent_engine.py: internal consents + grants/revocations

## Data Fixtures
- Consent notify payload: backend/consent_granted.json
- HI request payload: backend/health_information_request.json
- Other fixtures: backend/consent_notify.json

## Scripts
- m1_fast_test.sh: signed consent notify; requires ABDM_KEY_ID + TENANT_ID + abdm_private_key.pem + jq
- m2_fast_test.sh: signed HI request; requires ABDM_KEY_ID + TENANT_ID + abdm_private_key.pem + jq
- m3_fast_test.sh: signature replay/invalid/timestamp checks; requires ABDM_KEY_ID + TENANT_ID + PGPASSWORD for DB checks

## Tests
- Last test run: 2026-02-16 (pytest backend/tests/test_milestone3_signature_verification.py -q)
- Command: pytest backend/tests/test_milestone3_signature_verification.py -q
- Result: 6 passed
- Warnings: passlib crypt deprecation
- Test inventory:
  - test_consent_notify_schema.py: schema validation
  - test_consent_notify_integration.py: endpoint integration
  - test_signature_replay_and_errors.py: M3 signature error paths
  - test_milestone3_signature_verification.py: M3 end-to-end
  - test_internal_consent_engine.py: internal consent enforcement

## Feature Flags / Config
- STRICT_TENANT_MODE: true
- ABDM_TIMESTAMP_TOLERANCE_SECONDS: 300
- CORS_ORIGINS: http://localhost:5173

## API Surface (key routes)
- Auth: POST /api/auth/login, POST /api/auth/refresh
- ABDM: POST /abdm/consent/notify, POST /abdm/health-information/request
- Internal consent: POST /api/internal-consents/grant, POST /api/internal-consents/revoke
- Domain: GET /api/consents, GET /api/patients, GET/POST /api/records

## Security Model (M0–M3)
- JWT access + refresh tokens
- RBAC: SUPERADMIN, ADMIN, DOCTOR
- M3 signing: ECDSA P-256 request verification + response signing
- Replay protection: trusted_requests (tenant-scoped)
- Audit logging: audit_logs for ABDM + signature telemetry; no PHI

## Decisions / Rationale
- Tenant isolation: fail-closed; X-Tenant-ID required on all non-doc routes
- Consent immutability: consents insert-once; lifecycle in consent_events
- M3 security: ECDSA P-256 signatures + replay protection
- Encryption: envelope encryption, per-tenant DEK, tenant_keys table

## Encryption Model (Phase C)
- AES-256-GCM with AAD = tenant_id
- Envelope fields: v, alg, kid, nonce, ct
- tenant_keys holds wrapped DEK + key_version
- Lazy DEK creation on first encrypt; key_version enforced on decrypt

## Known Issues / Risks
- Functional: Alembic current fails because InternalConsent model uses reserved attribute name `metadata` (SQLAlchemy Declarative). Needs rename + migration fix.
- Security: KMS not configured for production (NullKMSClient)
- Performance: None noted

## Next Steps
1. Rename InternalConsent.metadata -> meta (or similar) + migration to fix Alembic load error.
2. Apply pending migrations to griva and griva_test.
3. Proceed Phase E (emergency access) after migration fix.

## Notes / Links
- Docs: /home/abel/myprojects/abdm/docs
- Tickets: N/A
