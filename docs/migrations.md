# Migration Integrity

## Purpose
This document describes how Alembic migrations are verified and how to validate that the database schema matches the repository state.

## Verification Commands
Run from `backend/`:

```
alembic current
alembic heads
alembic history --verbose
```

## Expected State
- Database revision equals Alembic head
- No pending migrations
- Clean upgrade path verified

## Fresh Database Validation
To validate migrations on a clean database:

1. Create an empty database.
2. Run:

```
alembic upgrade head
```

3. Verify current revision:

```
alembic current
```

4. Optionally compare schema snapshot:

```
pg_dump --schema-only --no-owner --no-privileges -h localhost -U griva -d <db_name> > docs/schema_snapshot.sql
```

## Notes
- Migrations are the only allowed mechanism for schema changes.
- Manual DDL changes are prohibited for compliance and auditability.

## Post-Remediation Migration Verification

Commands:
```
alembic current
alembic heads
```

Output:
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
a8eca30e6562
bf5cbea98598 (head)
```

## Database Upgrade Verification

Commands:
```
alembic current
alembic heads
```

Output:
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
bf5cbea98598 (head)
bf5cbea98598 (head)
```
