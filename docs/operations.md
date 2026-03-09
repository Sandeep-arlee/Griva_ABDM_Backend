# Operations (SOP)

## Deployment
1. Deploy application artifacts.
2. Verify environment configuration is present (DB, secrets, key material).
3. Run migrations using Alembic.
4. Start API server and verify health endpoints.

## Database Migration Procedure
1. Ensure backup is available.
2. Run:
   ```
   alembic upgrade head
   ```
3. Verify:
   ```
   alembic current
   ```

## Environment Configuration
- DATABASE_URL
- SECRET_KEY
- ABDM_PRIVATE_KEY_PEM
- ABDM_KEY_ID
- PLATFORM_IDENTITY_KEY_B64
- TENANT_MASTER_KEY_B64
- HPR OAuth variables

## API Startup
- Run application server with correct environment variables.
- Confirm middleware order and tenant enforcement.

## Failure Recovery
- Roll back to previous release if needed.
- Restore database from backup if data corruption is detected.

## Log Inspection
- Review structured security logs.
- Correlate audit logs with security events.

## Backup Strategy
- Daily encrypted backups for database and audit logs.
- Retain backups per compliance policy.

## Token Rotation / Secrets Handling
- Rotate JWT signing keys and ABDM keys as per policy.
- Rotate tenant master key only with re-encryption procedure.
- Never log secrets or decrypted PHI.
