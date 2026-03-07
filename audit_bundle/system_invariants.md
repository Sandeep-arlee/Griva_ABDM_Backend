# System Invariants

## Consent Lifecycle Invariants
- Consent status is stored in `consents.status`.
- All status transitions create a corresponding `consent_events` record.
- Consent events are append-only.
- Each consent event references a valid consent ID.

## Audit Log Invariants
- All write operations create an audit log entry.
- Audit logs are immutable.
- Timestamps are stored in UTC.

## Tenant Isolation Invariants
- All domain tables reference `tenant_id`.
- Cross-tenant access is forbidden.
- Foreign key constraints enforce tenant scoping.
- Loader criteria enforces tenant filtering for ORM queries.
- Raw SQL queries must include explicit tenant filters.

## Data Integrity Invariants
- Enums enforce valid state values.
- Unique constraints prevent duplicates (e.g., consent IDs, ABHA hash per tenant).
- `raw_payload` is stored as immutable JSONB.
