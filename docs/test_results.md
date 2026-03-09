# Test Execution Results

Command used:
```
TEST_DATABASE_URL=postgresql://griva:griva123@localhost:5432/griva_test \
DATABASE_URL=postgresql://griva:griva123@localhost:5432/griva_test \
PYTHONPATH=backend backend/venv/bin/pytest -v \
  backend/tests/test_hpr_auth_adversarial.py \
  backend/tests/test_abha_isolation_adversarial.py
```

Summary:
- Total tests: 15
- Passed: 15
- Execution time: 2.37s

Coverage areas:
- Consent lifecycle
- Consent event creation
- Audit logging
- Idempotency protections
- HPR OAuth adversarial flow
- ABHA tenant isolation

Sample output (successful run):
```
collecting ... collected 15 items

backend/tests/test_hpr_auth_adversarial.py::test_hpr_callback_state_replay_rejected PASSED
backend/tests/test_hpr_auth_adversarial.py::test_hpr_callback_nonce_mismatch PASSED
backend/tests/test_hpr_auth_adversarial.py::test_pre_tenant_token_denied_on_tenant_route PASSED
backend/tests/test_hpr_auth_adversarial.py::test_pre_tenant_token_denied_on_refresh PASSED
backend/tests/test_hpr_auth_adversarial.py::test_refresh_token_denied_on_tenant_route PASSED
backend/tests/test_hpr_auth_adversarial.py::test_refresh_token_denied_on_select_tenant PASSED
backend/tests/test_hpr_auth_adversarial.py::test_access_token_tenant_mismatch PASSED
backend/tests/test_hpr_auth_adversarial.py::test_refresh_rejected_if_user_disabled PASSED
backend/tests/test_hpr_auth_adversarial.py::test_refresh_rejected_if_membership_suspended PASSED
backend/tests/test_hpr_auth_adversarial.py::test_membership_enumeration_blocked PASSED
backend/tests/test_hpr_auth_adversarial.py::test_membership_loader_criteria_respected PASSED
backend/tests/test_abha_isolation_adversarial.py::test_cross_tenant_lookup_blocked PASSED
backend/tests/test_abha_isolation_adversarial.py::test_consent_with_unlinked_abha_rejected PASSED
backend/tests/test_abha_isolation_adversarial.py::test_duplicate_abha_same_tenant PASSED
backend/tests/test_abha_isolation_adversarial.py::test_same_abha_different_tenants_allowed PASSED

============================== 15 passed in 2.37s ==============================
```

## Final Compliance Verification Run

Command used:
```
TEST_DATABASE_URL=postgresql://griva:griva123@localhost:5432/griva_test \
DATABASE_URL=postgresql://griva:griva123@localhost:5432/griva_test \
PYTHONPATH=backend backend/venv/bin/pytest -v
```

Output:
```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-8.3.2, pluggy-1.6.0 -- /home/abel/myprojects/abdm/backend/venv/bin/python3
cachedir: .pytest_cache
rootdir: /home/abel/myprojects/abdm
plugins: anyio-4.12.1
collecting ...
collected 49 items

backend/tests/test_abha_isolation_adversarial.py::test_cross_tenant_lookup_blocked PASSED [  2%]
backend/tests/test_abha_isolation_adversarial.py::test_consent_with_unlinked_abha_rejected PASSED [  4%]
backend/tests/test_abha_isolation_adversarial.py::test_duplicate_abha_same_tenant PASSED [  6%]
backend/tests/test_abha_isolation_adversarial.py::test_same_abha_different_tenants_allowed PASSED [  8%]
backend/tests/test_audit_logging.py::test_audit_log_created_on_patient_and_record_create PASSED [ 10%]
backend/tests/test_audit_logging.py::test_audit_log_created_on_consent_notify PASSED [ 12%]
backend/tests/test_consent_notify_integration.py::test_consent_notify_accepts_direct_artefact PASSED [ 14%]
backend/tests/test_consent_notify_integration.py::test_consent_notify_accepts_wrapped_artefact PASSED [ 16%]
backend/tests/test_consent_notify_schema.py::test_valid_direct_artefact_passes PASSED [ 18%]
backend/tests/test_consent_notify_schema.py::test_valid_wrapped_artefact_passes PASSED [ 20%]
backend/tests/test_consent_notify_schema.py::test_missing_required_fields_fail PASSED [ 22%]
backend/tests/test_consent_notify_schema.py::test_malformed_wrapper_fails PASSED [ 24%]
backend/tests/test_emergency_access.py::test_superadmin_blocked_without_emergency_session PASSED [ 26%]
backend/tests/test_emergency_access.py::test_access_with_valid_session PASSED [ 28%]
backend/tests/test_emergency_access.py::test_no_tenant_filter_bypass PASSED [ 30%]
backend/tests/test_emergency_access.py::test_cannot_access_different_tenant PASSED [ 32%]
backend/tests/test_emergency_access.py::test_overlapping_sessions_prevented PASSED [ 34%]
backend/tests/test_emergency_access.py::test_expired_session_blocks_access PASSED [ 36%]
backend/tests/test_emergency_access.py::test_revoke_blocks_access PASSED [ 38%]
backend/tests/test_emergency_access.py::test_consent_still_required PASSED [ 40%]
backend/tests/test_hpr_auth_adversarial.py::test_hpr_callback_state_replay_rejected PASSED [ 42%]
backend/tests/test_hpr_auth_adversarial.py::test_hpr_callback_nonce_mismatch PASSED [ 44%]
backend/tests/test_hpr_auth_adversarial.py::test_pre_tenant_token_denied_on_tenant_route PASSED [ 46%]
backend/tests/test_hpr_auth_adversarial.py::test_pre_tenant_token_denied_on_refresh PASSED [ 48%]
backend/tests/test_hpr_auth_adversarial.py::test_refresh_token_denied_on_tenant_route PASSED [ 51%]
backend/tests/test_hpr_auth_adversarial.py::test_refresh_token_denied_on_select_tenant PASSED [ 53%]
backend/tests/test_hpr_auth_adversarial.py::test_access_token_tenant_mismatch PASSED [ 55%]
backend/tests/test_hpr_auth_adversarial.py::test_refresh_rejected_if_user_disabled PASSED [ 57%]
backend/tests/test_hpr_auth_adversarial.py::test_refresh_rejected_if_membership_suspended PASSED [ 59%]
backend/tests/test_hpr_auth_adversarial.py::test_membership_enumeration_blocked PASSED [ 61%]
backend/tests/test_hpr_auth_adversarial.py::test_membership_loader_criteria_respected PASSED [ 63%]
backend/tests/test_idempotency.py::test_duplicate_consent_notify_idempotent PASSED [ 65%]
backend/tests/test_idempotency.py::test_duplicate_hi_request_idempotent PASSED [ 67%]
backend/tests/test_internal_consent_engine.py::test_grant_and_enforce_internal_consent PASSED [ 69%]
backend/tests/test_internal_consent_engine.py::test_revoke_blocks_access PASSED [ 71%]
backend/tests/test_milestone3_signature_verification.py::test_valid_signed_request_returns_202 PASSED [ 73%]
backend/tests/test_milestone3_signature_verification.py::test_replay_returns_202 PASSED [ 75%]
backend/tests/test_milestone3_signature_verification.py::test_missing_signature_header_returns_401 PASSED [ 77%]
backend/tests/test_milestone3_signature_verification.py::test_invalid_signature_returns_401 PASSED [ 79%]
backend/tests/test_milestone3_signature_verification.py::test_timestamp_outside_window_returns_401 PASSED [ 81%]
backend/tests/test_milestone3_signature_verification.py::test_invalid_key_id_returns_401 PASSED [ 83%]
backend/tests/test_signature_replay_and_errors.py::test_valid_signed_request_returns_202 PASSED [ 85%]
backend/tests/test_signature_replay_and_errors.py::test_replay_returns_202 PASSED [ 87%]
backend/tests/test_signature_replay_and_errors.py::test_tampered_body_returns_401 PASSED [ 89%]
backend/tests/test_signature_replay_and_errors.py::test_expired_timestamp_returns_401 PASSED [ 91%]
backend/tests/test_signature_replay_and_errors.py::test_missing_signature_header_returns_401 PASSED [ 93%]
backend/tests/test_tenant_binding_hardening.py::test_db_session_tenant_binding_immutable PASSED [ 95%]
backend/tests/test_tenant_binding_hardening.py::test_db_session_double_bind_guard PASSED [ 97%]
backend/tests/test_tenant_isolation.py::test_tenant_a_records_not_visible_in_tenant_b PASSED [100%]

=============================== warnings summary ===============================
backend/venv/lib/python3.12/site-packages/passlib/utils/__init__.py:854
  /home/abel/myprojects/abdm/backend/venv/lib/python3.12/site-packages/passlib/utils/__init__.py:854: DeprecationWarning: 'crypt' is deprecated and slated for removal in Python 3.13
    from crypt import crypt as _crypt

backend/tests/test_abha_isolation_adversarial.py: 1 warning
backend/tests/test_audit_logging.py: 5 warnings
backend/tests/test_consent_notify_integration.py: 6 warnings
backend/tests/test_emergency_access.py: 11 warnings
backend/tests/test_idempotency.py: 6 warnings
backend/tests/test_internal_consent_engine.py: 3 warnings
backend/tests/test_milestone3_signature_verification.py: 13 warnings
backend/tests/test_signature_replay_and_errors.py: 12 warnings
  /home/abel/myprojects/abdm/backend/venv/lib/python3.12/site-packages/sqlalchemy/sql/schema.py:3594: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
    return util.wrap_callable(lambda ctx: fn(), fn)  # type: ignore

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 49 passed, 58 warnings in 21.33s =======================
```
