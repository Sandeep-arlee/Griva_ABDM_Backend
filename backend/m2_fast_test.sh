#!/usr/bin/env bash
set -euo pipefail

API_BASE="http://127.0.0.1:8000"
KEY_ID="${ABDM_KEY_ID}"
TENANT_ID="${TENANT_ID:-}"
PRIVATE_KEY_FILE="abdm_private_key.pem"
JSON_FILE="health_information_request.json"
HIP_ID="HIP123"
HIU_ID="HIU123"
CM_ID="cm.example"

if [[ -z "${KEY_ID}" ]]; then
  echo "ABDM_KEY_ID not set"
  exit 1
fi
if [[ -z "${TENANT_ID}" ]]; then
  echo "TENANT_ID not set"
  exit 1
fi

if [[ ! -f "${PRIVATE_KEY_FILE}" ]]; then
  echo "Private key file ${PRIVATE_KEY_FILE} not found"
  exit 1
fi

if [[ ! -f "${JSON_FILE}" ]]; then
  echo "JSON file ${JSON_FILE} not found"
  exit 1
fi

echo "Logging in..."

TOKEN=$(curl -fsS -X POST "$API_BASE/api/auth/login" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -d '{"email":"admin@example.com","password":"password"}' \
  | jq -r '.access_token')

[[ -z "$TOKEN" || "$TOKEN" == "null" ]] && echo "LOGIN FAILED" && exit 1

echo "Token acquired"

REQ_ID="hi-req-$(date -u +%s)"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

BODY=$(jq -cS --arg req "$REQ_ID" --arg ts "$TS" '.hiRequest.requestId=$req | .hiRequest.timestamp=$ts' "$JSON_FILE")
PYTHON_BIN="./venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

BODY_HASH=$(BODY="$BODY" $PYTHON_BIN - <<'PY'
import hashlib, os
body = os.environ["BODY"].encode("utf-8")
print(hashlib.sha256(body).hexdigest())
PY
)

CANONICAL="POST
/abdm/health-information/request
${REQ_ID}
${TS}
${BODY_HASH}"

SIGNATURE=$(CANONICAL="$CANONICAL" PRIVATE_KEY_FILE="$PRIVATE_KEY_FILE" $PYTHON_BIN - <<'PY'
import base64, os
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

canonical = os.environ["CANONICAL"].encode("utf-8")
key_path = os.environ["PRIVATE_KEY_FILE"]
private_key = serialization.load_pem_private_key(open(key_path, "rb").read(), password=None)
sig = private_key.sign(canonical, ec.ECDSA(hashes.SHA256()))
print(base64.b64encode(sig).decode("utf-8"))
PY
)

echo "Calling signed health-information request..."

curl -i -X POST "${API_BASE}/abdm/health-information/request" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-HIP-ID: ${HIP_ID}" \
  -H "X-HIU-ID: ${HIU_ID}" \
  -H "X-CM-ID: ${CM_ID}" \
  -H "X-Tenant-ID: ${TENANT_ID}" \
  -H "X-Request-ID: ${REQ_ID}" \
  -H "X-Timestamp: ${TS}" \
  -H "X-Key-Id: ${KEY_ID}" \
  -H "X-Signature: ${SIGNATURE}" \
  --data-binary "${BODY}"
