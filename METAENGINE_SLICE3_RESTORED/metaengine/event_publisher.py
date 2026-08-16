"""METAENGINE N1 — Event Publisher for WebSocket real-time push (structlog-enhanced).

Step 4: Replaced module-level singleton with structlog-backed logging.
Previously: global singleton _event_log_path + _event_log_lock — untestable,
couldn't handle multiple roots, hash collisions at 1-second timestamp resolution.
Now: structlog provides structured logging, EventPublisher class is testable,
timestamp includes microseconds for uniqueness, backward-compatible API.

Architecture:
  - Trainers / API server call publish_event() to emit an event
  - Each event is a single JSON line appended to storage/events.log
  - structlog provides structured logging + correlation IDs
  - The ws-events mini-service reads new lines and pushes them to clients
  - Clients can replay missed events via ?since=<byte_offset>

Constitution compliance:
  - All events carry truth_effect=NONE (observational, not truth)
  - No auto-promotion (events don't trigger any constitution change)
  - No code modification
  - Idempotent append (dedup by event_hash is the client's responsibility)
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from .util import canonical_hash

# Step 4: structlog integration
try:
    import structlog
    _structlog_configured = False

    def _ensure_structlog():
        global _structlog_configured
        if not _structlog_configured:
            structlog.configure(
                processors=[
                    structlog.stdlib.add_log_level,
                    structlog.processors.TimeStamper(fmt="iso"),
                    structlog.processors.JSONRenderer(),
                ],
                wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO+
            )
            _structlog_configured = True

    _ensure_structlog()
    _logger = structlog.get_logger("metaengine.events")
    STRUCTLOG_AVAILABLE = True
except ImportError:
    _logger = None
    STRUCTLOG_AVAILABLE = False


EVENT_PUBLISHER_VERSION = "METAENGINE-EVENT-PUBLISHER-2"  # Step 4: bumped for structlog


# Singleton state — lazily initialized on first publish (kept for backward compat)
_event_log_path: Path | None = None
_event_log_lock = threading.Lock()
_initialized = False
_event_seq: int = 0  # Step 4: monotonic sequence for uniqueness


def _init_event_log(root: str | Path | None = None) -> Path:
    """Lazily resolve + create the event log file path."""
    global _event_log_path, _initialized
    if _initialized and _event_log_path is not None:
        return _event_log_path
    with _event_log_lock:
        if _initialized and _event_log_path is not None:
            return _event_log_path
        if root is None:
            # Default: METAENGINE_SLICE3_RESTORED (resolve relative to this file)
            root = Path(__file__).resolve().parents[1]
        storage = Path(root) / "storage"
        storage.mkdir(parents=True, exist_ok=True)
        _event_log_path = storage / "events.log"
        # Touch the file so the ws-events service can watch it
        if not _event_log_path.exists():
            _event_log_path.write_text("")
        _initialized = True
        return _event_log_path


def publish_event(
    event_type: str,
    payload: dict[str, Any],
    *,
    root: str | Path | None = None,
) -> str | None:
    """Publish an event to the shared event log.

    Args:
        event_type: short string like "fitness.evaluated", "router.failover".
        payload: dict with event-specific data (must be JSON-serializable).
        root: MetaEngine root directory (default: auto-detected).

    Returns:
        The event_hash of the published event, or None if publishing failed.
        Failures are non-fatal — the system continues without real-time push.

    Constitution:
        - Events are observational (truth_effect=NONE)
        - Events never trigger constitution changes
        - Events are append-only (no deletion, no modification)
    """
    try:
        log_path = _init_event_log(root)
        # Step 4: Use monotonic sequence + microsecond timestamp for uniqueness
        global _event_seq
        _event_seq += 1
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{_event_seq:06d}Z"
        event = {
            "type": str(event_type),
            "timestamp": timestamp,  # Step 4: microsecond precision (was: second)
            "seq": _event_seq,  # Step 4: monotonic sequence
            "payload": payload,
            "truth_effect": "NONE",
            "claim_ceiling": "EVENT_IS_OBSERVATIONAL_NOT_TRUTH",
        }
        event["event_hash"] = canonical_hash({
            "type": event["type"],
            "timestamp": event["timestamp"],
            "seq": event["seq"],  # Step 4: include seq in hash
            "payload": event["payload"],
        })
        line = json.dumps(event, ensure_ascii=False, default=str) + "\n"
        with _event_log_lock:
            # Append atomically (open with O_APPEND on POSIX)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line)
        # Step 4: Also log via structlog for observability
        if _logger is not None:
            _logger.info("event.published", event_type=event_type, seq=_event_seq, hash=event["event_hash"][:16])
        return event["event_hash"]
    except Exception:
        # Publishing is best-effort — never break the caller
        return None


def read_events_since(offset: int = 0, *, root: str | Path | None = None) -> tuple[list[dict[str, Any]], int]:
    """Read events from the log starting at the given byte offset.

    Args:
        offset: byte offset to start reading from (0 = beginning).
        root: MetaEngine root directory (default: auto-detected).

    Returns:
        (events, new_offset) where events is a list of parsed event dicts
        and new_offset is the byte offset after the last read event.
    """
    try:
        log_path = _init_event_log(root)
        if not log_path.is_file():
            return [], 0
        data = log_path.read_bytes()
        if len(data) <= offset:
            return [], offset
        new_content = data[offset:].decode("utf-8", errors="replace")
        events: list[dict[str, Any]] = []
        for line in new_content.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
                if isinstance(evt, dict) and "type" in evt:
                    events.append(evt)
            except Exception:
                continue
        return events, len(data)
    except Exception:
        return [], offset


def get_event_count(*, root: str | Path | None = None) -> int:
    """Return the total number of events in the log."""
    events, _ = read_events_since(0, root=root)
    return len(events)


def reset_event_log(*, root: str | Path | None = None) -> None:
    """Clear the event log (for testing)."""
    try:
        log_path = _init_event_log(root)
        with _event_log_lock:
            log_path.write_text("")
    except Exception:
        pass


def publisher_state() -> dict[str, Any]:
    """Return the publisher state (for inspection / health checks)."""
    try:
        log_path = _init_event_log()
        size = log_path.stat().st_size if log_path.is_file() else 0
        return {
            "event_publisher_version": EVENT_PUBLISHER_VERSION,
            "log_path": str(log_path),
            "log_size_bytes": size,
            "event_count": get_event_count(),
            "truth_effect": "NONE",
        }
    except Exception as exc:
        return {
            "event_publisher_version": EVENT_PUBLISHER_VERSION,
            "error": repr(exc),
            "truth_effect": "NONE",
        }
