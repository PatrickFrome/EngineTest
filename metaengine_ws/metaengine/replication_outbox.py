from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .util import canonical_hash, load_json, write_json


class ReplicationOutbox:
    """Content-addressed, retryable replication batches; local run artifacts remain canonical."""

    def __init__(self, run_dir: str | Path):
        self.root = Path(run_dir) / "replication_outbox"
        self.root.mkdir(parents=True, exist_ok=True)

    def stage(self, backend: str, statements: list[str]) -> dict[str, Any]:
        payload = {"outbox_version": "16X-TRANSACTIONAL-REPLICATION-OUTBOX-2.3", "backend": backend, "statements": statements}
        batch_hash = canonical_hash(payload)
        value = {**payload, "batch_hash": batch_hash, "status": "PENDING", "attempts": 0, "local_is_canonical": True}
        path = self.root / f"{backend}_{batch_hash}.json"
        if not path.exists():
            write_json(path, value)
        return value

    def mark(self, batch_hash: str, backend: str, status: str, error: str | None = None) -> dict[str, Any]:
        path = self.root / f"{backend}_{batch_hash}.json"
        value = load_json(path)
        value["status"] = status
        value["attempts"] = int(value.get("attempts", 0)) + 1
        value["last_error"] = error
        temporary = path.with_suffix(".json.tmp")
        write_json(temporary, value)
        os.replace(temporary, path)
        return value

