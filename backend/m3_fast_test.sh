#!/usr/bin/env bash
set -euo pipefail

API_BASE="http://127.0.0.1:8000"
KEY_ID="${ABDM_KEY_ID}"
TENANT_ID="${TENANT_ID:-}"
PRIVATE_KEY_FILE="abdm_private_key.pem"
JSON_FILE="consent_granted.json"
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

PYTHON_BIN="./venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

echo "Logging in..."
TOKEN=$(curl -fsS -X POST "$API_BASE/api/auth/login" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -d '{"email":"admin@example.com","password":"password"}' \
  | jq -r '.access_token')

[[ -z "$TOKEN" || "$TOKEN" == "null" ]] && echo "LOGIN FAILED" && exit 1

echo "Token acquired"

REQ_ID="m3-req-$(date -u +%s)"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

BODY=$(jq -cS --arg req "$REQ_ID" --arg ts "$TS" '.requestId=$req | .timestamp=$ts' "$JSON_FILE")

BODY_HASH=$(BODY="$BODY" $PYTHON_BIN - <<'PY'
import hashlib, os
body = os.environ["BODY"].encode("utf-8")
print(hashlib.sha256(body).hexdigest())
PY
)

CANONICAL="POST
/abdm/consent/notify
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

headers=(
  -H "Authorization: Bearer $TOKEN"
  -H "Content-Type: application/json"
  -H "X-HIP-ID: $HIP_ID"
  -H "X-HIU-ID: $HIU_ID"
  -H "X-CM-ID: $CM_ID"
  -H "X-Tenant-ID: $TENANT_ID"
  -H "X-Request-ID: $REQ_ID"
  -H "X-Timestamp: $TS"
  -H "X-Key-Id: $KEY_ID"
  -H "X-Signature: $SIGNATURE"
)

echo "1) Valid signed request (expect 202)"
curl -sS -i -X POST "$API_BASE/abdm/consent/notify" \
  "${headers[@]}" \
  --data-binary "$BODY"


echo -e "\n2) Replay (expect 409)"
curl -sS -i -X POST "$API_BASE/abdm/consent/notify" \
  "${headers[@]}" \
  --data-binary "$BODY"


echo -e "\n3) Missing signature (expect 401 MISSING_SIGNATURE)"
curl -sS -i -X POST "$API_BASE/abdm/consent/notify" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-HIP-ID: $HIP_ID" \
  -H "X-HIU-ID: $HIU_ID" \
  -H "X-CM-ID: $CM_ID" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -H "X-Request-ID: $REQ_ID-missing" \
  -H "X-Timestamp: $TS" \
  -H "X-Key-Id: $KEY_ID" \
  --data-binary "$BODY"


echo -e "\n4) Tampered body (expect 401 INVALID_SIGNATURE)"
TAMPERED=$(jq -cS '.notification.consentRequestId="TAMPERED"' <<<"$BODY")
curl -sS -i -X POST "$API_BASE/abdm/consent/notify" \
  "${headers[@]}" \
  --data-binary "$TAMPERED"


echo -e "\n5) Old timestamp (expect 401 TIMESTAMP_OUT_OF_RANGE)"
OLD_TS=$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ)
OLD_BODY=$(jq -cS --arg req "m3-old-$(date -u +%s)" --arg ts "$OLD_TS" '.requestId=$req | .timestamp=$ts' "$JSON_FILE")
OLD_HASH=$(BODY="$OLD_BODY" $PYTHON_BIN - <<'PY'
import hashlib, os
print(hashlib.sha256(os.environ["BODY"].encode("utf-8")).hexdigest())
PY
)
OLD_CANONICAL="POST
/abdm/consent/notify
$(jq -r '.requestId' <<<"$OLD_BODY")
${OLD_TS}
${OLD_HASH}"
OLD_SIGNATURE=$(CANONICAL="$OLD_CANONICAL" PRIVATE_KEY_FILE="$PRIVATE_KEY_FILE" $PYTHON_BIN - <<'PY'
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

curl -sS -i -X POST "$API_BASE/abdm/consent/notify" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-HIP-ID: $HIP_ID" \
  -H "X-HIU-ID: $HIU_ID" \
  -H "X-CM-ID: $CM_ID" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -H "X-Request-ID: $(jq -r '.requestId' <<<"$OLD_BODY")" \
  -H "X-Timestamp: $OLD_TS" \
  -H "X-Key-Id: $KEY_ID" \
  -H "X-Signature: $OLD_SIGNATURE" \
  --data-binary "$OLD_BODY"

echo -e "\n6) DB checks (audit + replay)"
if [[ -z "${PGPASSWORD:-}" ]]; then
  echo "PGPASSWORD not set; DB checks skipped"
  exit 0
fi

psql -U griva -d griva -c "select count(*) as signature_audit_count from audit_logs where event_type='ABDM_SIGNATURE';"
psql -U griva -d griva -c "select count(*) as trusted_requests_count from trusted_requests;"
psql -U griva -d griva -c \"select request_id, meta->>'outcome' as outcome, timestamp from audit_logs where event_type='ABDM_SIGNATURE' order by timestamp desc limit 5;\"
