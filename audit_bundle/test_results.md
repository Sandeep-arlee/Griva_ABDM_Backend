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

## Final Release Verification

Command used:
TEST_DATABASE_URL=postgresql://griva:griva123@localhost:5432/griva_test \
DATABASE_URL=postgresql://griva:griva123@localhost:5432/griva_test \
PYTHONPATH=backend backend/venv/bin/pytest -v \
backend/tests/test_hpr_auth_adversarial.py \
backend/tests/test_abha_isolation_adversarial.py

Output:
```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-8.3.2, pluggy-1.6.0 -- /home/abel/myprojects/abdm/backend/venv/bin/python3
cachedir: .pytest_cache
rootdir: /home/abel/myprojects/abdm/backend
configfile: pytest.ini
plugins: anyio-4.12.1
collecting ...
collected 15 items

backend/tests/test_hpr_auth_adversarial.py::test_hpr_callback_state_replay_rejected PASSED [  6%]
backend/tests/test_hpr_auth_adversarial.py::test_hpr_callback_nonce_mismatch PASSED [ 13%]
backend/tests/test_hpr_auth_adversarial.py::test_pre_tenant_token_denied_on_tenant_route PASSED [ 20%]
backend/tests/test_hpr_auth_adversarial.py::test_pre_tenant_token_denied_on_refresh PASSED [ 26%]
backend/tests/test_hpr_auth_adversarial.py::test_refresh_token_denied_on_tenant_route PASSED [ 33%]
backend/tests/test_hpr_auth_adversarial.py::test_refresh_token_denied_on_select_tenant PASSED [ 40%]
backend/tests/test_hpr_auth_adversarial.py::test_access_token_tenant_mismatch PASSED [ 46%]
backend/tests/test_hpr_auth_adversarial.py::test_refresh_rejected_if_user_disabled PASSED [ 53%]
backend/tests/test_hpr_auth_adversarial.py::test_refresh_rejected_if_membership_suspended PASSED [ 60%]
backend/tests/test_hpr_auth_adversarial.py::test_membership_enumeration_blocked PASSED [ 66%]
backend/tests/test_hpr_auth_adversarial.py::test_membership_loader_criteria_respected PASSED [ 73%]
backend/tests/test_abha_isolation_adversarial.py::test_cross_tenant_lookup_blocked PASSED [ 80%]
backend/tests/test_abha_isolation_adversarial.py::test_consent_with_unlinked_abha_rejected PASSED [ 86%]
backend/tests/test_abha_isolation_adversarial.py::test_duplicate_abha_same_tenant PASSED [ 93%]
backend/tests/test_abha_isolation_adversarial.py::test_same_abha_different_tenants_allowed PASSED [100%]

============================== 15 passed in 2.51s ==============================
```
