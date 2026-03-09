# System Verification Remediation Report

## Issues Detected
- ConsentEvent lifecycle model lacked explicit `old_status` and `new_status` fields.
- AuditLog model missing required fields (`actor`, `action`, `resource_type`, `resource_id`).
- `consent_events.tenant_id` and `patients.tenant_id` were nullable, weakening tenant isolation.
- HPR OAuth flow created users with null email/password/role, violating DB constraints.
- Emergency access service failed when request IP was not a valid INET (e.g., test client host).
- Adversarial tests required tenant-aware ABHA linkage to pass consent notify validation.

## Changes Implemented
- Added `old_status` and `new_status` to ConsentEvent and ensured they use the Consent status enum.
- Added missing AuditLog fields and enforced non-null audit log metadata across write paths.
- Enforced tenant_id on consent_events and patients via migration with safe backfills.
- Updated HPR callback to create minimal global identity users without email/password/role.
- Normalized emergency access IPs to valid INET values before persistence.
- Added ABHA linkage setup in signature verification tests.
- Updated emergency access tests to use v2 sessions and align with emergency gating semantics.
- Hardened tenant loader criteria to apply consistently and included explicit membership filtering in tests.

## Migrations Added
- `730ef072bea7_compliance_remediation_consent_events_audit_logs_tenant_isolation`
  - Adds ConsentEvent `old_status`/`new_status`.
  - Adds AuditLog `actor`/`action`/`resource_type`/`resource_id`.
  - Backfills consent_events tenant_id and patient tenant_id.
  - Enforces NOT NULL constraints for required fields.

## Tests Executed
Command:
```
TEST_DATABASE_URL=postgresql://griva:griva123@localhost:5432/griva_test \
PYTHONPATH=backend backend/venv/bin/pytest -q
```

Result:
- 44 passed
- 41 warnings (SQLAlchemy UTC deprecation, passlib crypt deprecation)

## Final Compliance Status
COMPLIANT

## Notes
- Tenant isolation is enforced at both application and database layers.
- Consent lifecycle now records explicit status transitions.
- Audit logging is complete for all write paths.
- Tests execute against a dedicated `_test` database with migrations applied from scratch.
