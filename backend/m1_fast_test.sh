#!/usr/bin/env bash
set -e

API_BASE="http://127.0.0.1:8000"

echo "Logging in..."

TOKEN=$(curl -fsS -X POST "$API_BASE/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "password"
  }' | jq -r '.access_token')

if [[ -z "$TOKEN" || "$TOKEN" == "null" ]]; then
  echo "LOGIN FAILED"
  exit 1
fi

echo "Token acquired"

echo "Calling consent notify..."

curl -i -X POST "$API_BASE/abdm/consent/notify" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-HIP-ID: HIP123" \
  -H "X-HIU-ID: HIU123" \
  -H "X-CM-ID: cm.example" \
  -H "X-Request-ID: req-consent-001" \
  -H "X-Timestamp: 2024-01-01T10:00:00Z" \
  --data-binary @consent_granted.json
