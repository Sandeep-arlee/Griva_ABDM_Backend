#!/usr/bin/env bash
set -euo pipefail

API_BASE="http://127.0.0.1:8000"
JSON_FILE="health_information_request.json"

# These MUST match the consent artefact from M1
HIP_ID="HIP123"
HIU_ID="HIU123"
CM_ID="CM_001"

echo "==> Step 1: Authenticate and export TOKEN"

TOKEN=$(curl -fsS -X POST "${API_BASE}/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "password"
  }' | jq -r '.access_token')

if [[ -z "${TOKEN}" || "${TOKEN}" == "null" ]]; then
  echo "FAIL: Could not obtain access token"
  exit 1
fi

export TOKEN
echo "PASS: TOKEN obtained"

echo
echo "==> Step 2: Validate ${JSON_FILE} exists"

if [[ ! -f "${JSON_FILE}" ]]; then
  echo "FAIL: ${JSON_FILE} not found"
  exit 1
fi

echo "PASS: ${JSON_FILE} found"

echo
echo "==> Step 3: Extract requestId and timestamp from JSON"

REQ_ID=$(jq -r '.hiRequest.requestId' "${JSON_FILE}")
TS=$(jq -r '.hiRequest.timestamp' "${JSON_FILE}")

if [[ -z "${REQ_ID}" || "${REQ_ID}" == "null" ]]; then
  echo "FAIL: requestId missing in JSON"
  exit 1
fi

if [[ -z "${TS}" || "${TS}" == "null" ]]; then
  echo "FAIL: timestamp missing in JSON"
  exit 1
fi

echo "PASS: requestId=${REQ_ID}, timestamp=${TS}"

echo
echo "==> Step 4: POST /abdm/health-information/request"

HTTP_RESPONSE=$(curl -sS -i -w "\nHTTP_STATUS:%{http_code}\n" \
  -X POST "${API_BASE}/abdm/health-information/request" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-HIP-ID: ${HIP_ID}" \
  -H "X-HIU-ID: ${HIU_ID}" \
  -H "X-CM-ID: ${CM_ID}" \
  -H "X-Request-ID: ${REQ_ID}" \
  -H "X-Timestamp: ${TS}" \
  --data-binary @"${JSON_FILE}")

echo "${HTTP_RESPONSE}"

STATUS=$(echo "${HTTP_RESPONSE}" | sed -n 's/HTTP_STATUS://p')

if [[ "${STATUS}" == "202" ]]; then
  echo "PASS: Received 202 Accepted"
else
  echo "FAIL: Expected 202, got ${STATUS}"
  exit 1
fi

echo
echo "==> Step 5: Database verification (manual)"

cat <<EOM
Run the following SQL:

  select count(*) from health_information_requests;
  select count(*) from health_information_events;
  select count(*) from audit_logs;

Expected:
  health_information_requests = 1
  health_information_events   >= 1
  audit_logs                  incremented
EOM

echo "==> M2 FAST TEST COMPLETED"
