#!/usr/bin/env bash
set -euo pipefail

DB_NAME="abdm_test"
PGHOST="${PGHOST:-localhost}"
PGUSER="${PGUSER:-griva}"
PGPASSWORD="${PGPASSWORD:-griva123}"
export PGPASSWORD

if command -v dropdb >/dev/null 2>&1; then
  dropdb -h "$PGHOST" -U "$PGUSER" --if-exists "$DB_NAME"
fi

createdb -h "$PGHOST" -U "$PGUSER" "$DB_NAME"

DATABASE_URL="postgresql://${PGUSER}:${PGPASSWORD}@${PGHOST}:5432/${DB_NAME}" \
  (cd backend && alembic upgrade head)

echo "Fresh migration completed on ${DB_NAME}."
