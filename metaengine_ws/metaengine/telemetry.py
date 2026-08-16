from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .security import redact_secrets
from .util import canonical_hash, write_json


class TelemetryLedger:
    """Thread-safe run telemetry. Unknown token/USD data remains missing, never zero-filled."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.started = time.perf_counter()
        self.events: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def record(self, kind: str, **fields: Any) -> dict[str, Any]:
        clean = {}
        for key, value in fields.items():
            clean[key] = redact_secrets(value) if isinstance(value, str) else value
        with self._lock:
            previous = self.events[-1]["event_hash"] if self.events else None
            event = {
                "ordinal": len(self.events) + 1,
                "run_id": self.run_id,
                "kind": kind,
                "monotonic_seconds": round(time.perf_counter() - self.started, 6),
                "previous_event_hash": previous,
                **clean,
            }
            event["event_hash"] = canonical_hash(event)
            self.events.append(event)
            return event

    @contextmanager
    def span(self, kind: str, **fields: Any):
        started = time.perf_counter()
        self.record(kind + "_START", **fields)
        try:
            yield
        except Exception as exc:
            self.record(kind + "_FAILED", wall_seconds=round(time.perf_counter() - started, 6), error=repr(exc), **fields)
            raise
        else:
            self.record(kind + "_COMPLETE", wall_seconds=round(time.perf_counter() - started, 6), **fields)

    def artifact(self) -> dict[str, Any]:
        wall = round(time.perf_counter() - self.started, 6)
        value = {
            "telemetry_version": "16X-RUN-TELEMETRY-2.3",
            "run_id": self.run_id,
            "wall_seconds": wall,
            "events": list(self.events),
            "token_coverage": "MISSING_UNLESS_REPORTED_BY_REAL_ADAPTER",
            "usd_coverage": "MISSING_UNLESS_REPORTED_BY_REAL_ADAPTER",
            "claim_ceiling": "TELEMETRY_MEASURES_EXECUTION_NOT_EPISTEMIC_QUALITY",
        }
        value["telemetry_hash"] = canonical_hash(value)
        return value

    def write(self, path: str | Path) -> dict[str, Any]:
        value = self.artifact()
        write_json(path, value)
        return value

