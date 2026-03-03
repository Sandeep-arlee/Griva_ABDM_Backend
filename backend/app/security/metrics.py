from __future__ import annotations

import threading


class SecurityMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.emergency_sessions_created_total = 0
        self.emergency_decrypt_total = 0
        self.emergency_export_total = 0
        self.emergency_cap_exceeded_total = 0

    def inc(self, field: str, value: int = 1) -> None:
        with self._lock:
            current = getattr(self, field)
            setattr(self, field, current + value)

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "emergency_sessions_created_total": self.emergency_sessions_created_total,
                "emergency_decrypt_total": self.emergency_decrypt_total,
                "emergency_export_total": self.emergency_export_total,
                "emergency_cap_exceeded_total": self.emergency_cap_exceeded_total,
            }


security_metrics = SecurityMetrics()
