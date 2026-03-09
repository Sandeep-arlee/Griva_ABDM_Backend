# Archive Verification

Command:
unzip -l abdm-hip-backend-audit-bundle-v1.0.0.zip

Output:
```
Archive:  abdm-hip-backend-audit-bundle-v1.0.0.zip
  Length      Date    Time    Name
---------  ---------- -----   ----
        0  2026-03-07 11:03   audit_bundle/
      893  2026-03-06 16:25   audit_bundle/migrations.md
    37694  2026-03-06 16:25   audit_bundle/schema_snapshot.sql
      487  2026-03-06 16:26   audit_bundle/release_notes.md
      753  2026-03-06 16:25   audit_bundle/security_checklist.md
      781  2026-03-06 16:25   audit_bundle/architecture.md
      869  2026-03-06 16:25   audit_bundle/system_invariants.md
     4348  2026-03-07 11:03   audit_bundle/test_results.md
      262  2026-03-06 16:26   audit_bundle/architecture_diagram.md
      625  2026-03-07 11:03   audit_bundle/project_summary.md
      258  2026-03-07 11:03   audit_bundle/migration_verification.md
      260  2026-03-06 16:26   audit_bundle/release_process.md
     1210  2026-03-06 16:25   audit_bundle/operations.md
---------                     -------
    48440                     13 files
```

## Post-Remediation Verification

Command:
```
unzip -l abdm-hip-backend-audit-bundle-v1.0.0.zip
```

Output:
```
Archive:  abdm-hip-backend-audit-bundle-v1.0.0.zip
  Length      Date    Time    Name
---------  ---------- -----   ----
        0  2026-03-07 11:03   audit_bundle/
      893  2026-03-06 16:25   audit_bundle/migrations.md
    37694  2026-03-06 16:25   audit_bundle/schema_snapshot.sql
      487  2026-03-06 16:26   audit_bundle/release_notes.md
      753  2026-03-06 16:25   audit_bundle/security_checklist.md
      781  2026-03-06 16:25   audit_bundle/architecture.md
      869  2026-03-06 16:25   audit_bundle/system_invariants.md
     4348  2026-03-07 11:03   audit_bundle/test_results.md
      262  2026-03-06 16:26   audit_bundle/architecture_diagram.md
      625  2026-03-07 11:03   audit_bundle/project_summary.md
      258  2026-03-07 11:03   audit_bundle/migration_verification.md
      260  2026-03-06 16:26   audit_bundle/release_process.md
     1210  2026-03-06 16:25   audit_bundle/operations.md
---------                     -------
    48440                     13 files
```

## Final Release Verification

Command:
```
unzip -l abdm-hip-backend-audit-bundle-v1.1.0.zip
```

Output:
```
Archive:  abdm-hip-backend-audit-bundle-v1.1.0.zip
  Length      Date    Time    Name
---------  ---------- -----   ----
        0  2026-03-09 14:53   audit_bundle/
      330  2026-03-07 13:12   audit_bundle/verification_instructions.md
     2191  2026-03-09 14:52   audit_bundle/archive_verification.md
      893  2026-03-06 16:25   audit_bundle/migrations.md
    37694  2026-03-06 16:25   audit_bundle/schema_snapshot.sql
      487  2026-03-06 16:26   audit_bundle/release_notes.md
      753  2026-03-06 16:25   audit_bundle/security_checklist.md
      781  2026-03-06 16:25   audit_bundle/architecture.md
      869  2026-03-06 16:25   audit_bundle/system_invariants.md
     4348  2026-03-07 11:03   audit_bundle/test_results.md
     1045  2026-03-07 13:12   audit_bundle/external_audit_summary.md
      657  2026-03-07 13:12   audit_bundle/audit_evidence_index.md
      670  2026-03-07 13:12   audit_bundle/final_release_summary.md
      262  2026-03-06 16:26   audit_bundle/architecture_diagram.md
      246  2026-03-07 11:19   audit_bundle/release_metadata.md
      625  2026-03-07 11:03   audit_bundle/project_summary.md
      646  2026-03-07 11:19   audit_bundle/manifest.md
      258  2026-03-07 11:03   audit_bundle/migration_verification.md
      260  2026-03-06 16:26   audit_bundle/release_process.md
     2095  2026-03-09 15:39   audit_bundle/checksums.sha256
      322  2026-03-09 15:39   audit_bundle/final_verification_snapshot.md
     1210  2026-03-06 16:25   audit_bundle/operations.md
---------                     -------
    56642                     22 files
```
