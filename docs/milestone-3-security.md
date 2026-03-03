# Milestone-3 Security

## Threat model
- Prevent request tampering and replay across ABDM integrations.
- Ensure only trusted public keys can authorize inbound requests.
- Guarantee outbound responses are signed and verifiable by HIU/CM.

## Key management strategy
- Public keys are stored in `trusted_keys` and loaded at runtime.
- Key rotation: mark old keys `is_active = false` and insert new key rows.
- Private key is provided via environment variable (no hardcoding).

## Signature canonicalization
**Inbound requests**:
```
HTTP_METHOD
REQUEST_PATH
X-Request-ID
X-Timestamp
SHA256(body)
```

**Outbound responses**:
```
HTTP_STATUS
REQUEST_PATH
X-Request-ID
X-Timestamp
SHA256(body)
```

## Error codes

| Condition                 | HTTP Status | Error Code             |
| ------------------------- | ----------- | ---------------------- |
| Missing signature headers | 401         | MISSING_SIGNATURE      |
| Invalid signature         | 401         | INVALID_SIGNATURE      |
| Timestamp outside window  | 401         | TIMESTAMP_OUT_OF_RANGE |
| Replay detected           | 409         | REPLAY_DETECTED        |

## Replay protection design
- Persist `(request_id, signature)` in `trusted_requests`.
- Reject duplicates with HTTP 409 Conflict.
- Enforce timestamp tolerance (±5 minutes).

## Telemetry
- Log verification success/failure in audit logs.
- Replay detection emits audit entry and returns 409.
