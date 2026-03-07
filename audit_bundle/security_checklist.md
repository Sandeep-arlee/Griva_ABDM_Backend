# Security & Compliance Checklist

## Authentication
- [ ] JWT signature validation enabled
- [ ] Token expiry enforced
- [ ] Refresh token rotation enforced

## Authorization
- [ ] Tenant isolation enforced on all routes
- [ ] Role checks applied to protected endpoints
- [ ] Emergency access enforced for SUPER_ADMIN on PHI routes

## Data Protection
- [ ] PHI stored in secure database
- [ ] ABHA encrypted at rest
- [ ] TLS enforced for database connection
- [ ] Secrets not logged

## Auditability
- [ ] Audit logs generated for all writes
- [ ] Audit logs immutable
- [ ] Emergency events recorded with DB time

## Infrastructure
- [ ] Schema changes via migrations only
- [ ] No manual DB modifications
- [ ] Backups and retention policy defined
