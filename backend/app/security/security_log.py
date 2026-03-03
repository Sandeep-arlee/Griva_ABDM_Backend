from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

_SECURITY_LOGGER = logging.getLogger("griva.security")
_SECURITY_LOGGER.propagate = False


def log_emergency_event(
    *,
    event_type: str,
    tenant_id: str,
    super_admin_id: str,
    session_id: str,
    ip: str | None,
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "category": "security",
        "type": "emergency_event",
        "event_type": event_type,
        "tenant_id": tenant_id,
        "super_admin_id": super_admin_id,
        "session_id": session_id,
        "ip": ip or "0.0.0.0",
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        payload.update(extra)
    _SECURITY_LOGGER.info(json.dumps(payload, separators=(",", ":"), sort_keys=True))
