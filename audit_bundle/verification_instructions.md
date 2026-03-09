# Audit Bundle Verification Instructions

Verify archive contents:

unzip -l abdm-hip-backend-audit-bundle-v1.0.0.zip

Verify SHA256 checksums:

sha256sum -c checksums.sha256

Verify git tags:

git tag
git show v1.0.0
git show v1.0.1

Verify migration state:

alembic current
alembic heads

Verify tests:

pytest -v backend/tests
