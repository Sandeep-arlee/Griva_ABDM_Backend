# Release Process

Commit evidence artifacts

git add audit_bundle
git commit -m "Stage 3: audit bundle and release packaging"

Create release tag

git tag v1.0.0

Create distributable audit bundle

zip -r abdm-hip-backend-audit-bundle-v1.0.0.zip audit_bundle
