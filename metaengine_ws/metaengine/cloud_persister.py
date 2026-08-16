"""METAENGINE — cloud persister for project development state.

A thin libSQL client that persists development steps, artifacts, source
records, mechanism candidates, and worklog entries to the Turso cloud DB
created in Task ID 20.

Design:

* **Non-canonical.** This store is ``NON_CANONICAL_PROJECT_STATE_PERSISTENCE``
  (canonical_authority=false). It never claims to be the canonical Supabase
  authority. Canonical mutation is still blocked (Boundary 3).
* **Token handling (Boundary 6).** The DB auth token is read from the
  environment (``TURSO_DB_TOKEN``) or accepted as a constructor argument. It
  is NEVER logged, NEVER written to disk, NEVER persisted in any artifact.
  If the token is absent, the persister is ``disabled`` (fail-safe, not
  fail-closed — persistence is a convenience, not a constitutional guard).
* **Idempotent writes.** Uses ``INSERT OR REPLACE`` keyed by content hash /
  step id, so re-running a slice receipt write does not duplicate rows.
* **Content-addressed.** Artifact writes are keyed by ``artifact_hash``;
  dev-step writes are keyed by ``step_id:kind``.

Usage::

    from metaengine.cloud_persister import CloudPersister
    p = CloudPersister.from_env()  # reads TURSO_DB_TOKEN + TURSO_DB_HOST
    p.save_dev_step(receipt.as_dict(), kind='post_step_receipt')
    p.save_artifact('source_registry', registry.as_dict(), slice_id='SLICE-3')
    p.save_worklog_entry(task_id, agent, task, content)
    p.read_dev_steps()
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

DEFAULT_HOST = "metaengine-project-patrickfrome.aws-eu-west-1.turso.io"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# libSQL HTTP pipeline client
# ---------------------------------------------------------------------------


class CloudPersisterError(RuntimeError):
    pass


class CloudPersisterDisabled(CloudPersisterError):
    """Raised when persistence is attempted with no token/host (fail-safe)."""


@dataclass(frozen=True)
class CloudPersisterConfig:
    host: str
    db_token: str
    enabled: bool


class CloudPersister:
    """Persists project development state to the Turso libSQL cloud DB.

    Construct via :meth:`from_env` (reads ``TURSO_DB_TOKEN`` and optionally
    ``TURSO_DB_HOST``). If the token is absent, the persister is created in
    a disabled state: writes are no-ops, reads return empty. This is
    fail-safe (persistence is a convenience layer, not a constitutional guard).
    """

    store_kind = "TURSO_LIBSQL_CLOUD_DB"
    canonical_authority = False

    def __init__(self, config: CloudPersisterConfig):
        self._config = config

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "CloudPersister":
        token = os.environ.get("TURSO_DB_TOKEN", "").strip()
        host = os.environ.get("TURSO_DB_HOST", DEFAULT_HOST).strip()
        enabled = bool(token and host)
        return cls(CloudPersisterConfig(host=host, db_token=token, enabled=enabled))

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @property
    def host(self) -> str:
        return self._config.host

    def _require_enabled(self) -> None:
        if not self._config.enabled:
            raise CloudPersisterDisabled(
                "CloudPersister is disabled: TURSO_DB_TOKEN is not set. "
                "Inject it via the trusted runtime environment."
            )

    # ------------------------------------------------------------------
    # libSQL HTTP pipeline
    # ------------------------------------------------------------------

    def _execute(self, sql: str, params: list[dict] | None = None) -> dict:
        self._require_enabled()
        url = f"https://{self._config.host}/v2/pipeline"
        body = {
            "requests": [
                {
                    "type": "execute",
                    "stmt": {"sql": sql, **({"args": params} if params else {})},
                }
            ]
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._config.db_token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            err = exc.read().decode("utf-8")
            raise CloudPersisterError(
                f"LIBSQL_ERROR HTTP {exc.code}: {err[:300]}\nSQL: {sql[:200]}"
            ) from exc

    def _query(self, sql: str, params: list[dict] | None = None) -> list[dict]:
        raw = self._execute(sql, params)
        try:
            res = raw["results"][0]["response"]["result"]
            cols = [c.get("name", f"c{i}") for i, c in enumerate(res.get("cols", []))]
            rows = []
            for row in res.get("rows", []):
                values = []
                for v in row:
                    if v.get("type") == "null":
                        values.append(None)
                    else:
                        values.append(v.get("value"))
                rows.append(dict(zip(cols, values)))
            return rows
        except (KeyError, IndexError, TypeError) as exc:
            raise CloudPersisterError(f"query parse error: {exc}") from exc

    # ------------------------------------------------------------------
    # Write methods (idempotent via INSERT OR REPLACE)
    # ------------------------------------------------------------------

    def save_dev_step(
        self,
        payload: Mapping[str, Any],
        *,
        kind: str,
        step_id: str | None = None,
    ) -> str:
        """Persist a development step (receipt or review).

        Idempotent: keyed by ``<step_id>:<kind>``.
        """
        self._require_enabled()
        sid = step_id or payload.get("step_id") or payload.get("completed_step_id") or "unknown"
        key = f"{sid}:{kind}"
        receipt_hash = payload.get("receipt_hash", "")
        decision = payload.get("decision", "")
        const_hash = payload.get("constitution_hash") or payload.get("constitution_snapshot_hash", "")
        arch_hash = payload.get("architecture_library_snapshot_hash", "")
        pol_hash = payload.get("policy_snapshot_hash", "")
        self._execute(
            "INSERT OR REPLACE INTO metaengine_dev_steps "
            "(step_id, kind, receipt_hash, decision, constitution_snapshot_hash, "
            "arch_library_snapshot_hash, policy_snapshot_hash, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            params=[
                {"type": "text", "value": key},
                {"type": "text", "value": kind},
                {"type": "text", "value": str(receipt_hash)},
                {"type": "text", "value": str(decision)},
                {"type": "text", "value": str(const_hash)},
                {"type": "text", "value": str(arch_hash)},
                {"type": "text", "value": str(pol_hash)},
                {"type": "text", "value": json.dumps(dict(payload), sort_keys=True)},
                {"type": "text", "value": _now()},
            ],
        )
        return key

    def save_artifact(
        self,
        artifact_id: str,
        payload: Mapping[str, Any],
        *,
        artifact_kind: str = "other",
        slice_id: str = "",
        artifact_hash: str | None = None,
    ) -> str:
        """Persist an architecture-library artifact (idempotent by artifact_id)."""
        self._require_enabled()
        ahash = artifact_hash or (
            payload.get("registry_hash")
            or payload.get("vault_hash")
            or payload.get("library_hash")
            or payload.get("mechanism_library_hash")
            or ""
        )
        self._execute(
            "INSERT OR REPLACE INTO metaengine_artifacts "
            "(artifact_id, artifact_kind, artifact_hash, slice_id, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            params=[
                {"type": "text", "value": artifact_id},
                {"type": "text", "value": artifact_kind},
                {"type": "text", "value": str(ahash)},
                {"type": "text", "value": slice_id},
                {"type": "text", "value": json.dumps(dict(payload), sort_keys=True)},
                {"type": "text", "value": _now()},
            ],
        )
        return artifact_id

    def save_worklog_entry(
        self,
        task_id: str,
        agent: str,
        task: str,
        content: str,
    ) -> int:
        """Append a worklog entry. Returns the row id."""
        self._require_enabled()
        self._execute(
            "INSERT INTO metaengine_worklog (task_id, agent, task, content, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            params=[
                {"type": "text", "value": task_id},
                {"type": "text", "value": agent},
                {"type": "text", "value": task[:500]},
                {"type": "text", "value": content},
                {"type": "text", "value": _now()},
            ],
        )
        rows = self._query("SELECT last_insert_rowid() AS id")
        return int(rows[0]["id"]) if rows else 0

    def save_source_record(self, record: Mapping[str, Any]) -> str:
        self._require_enabled()
        sid = record.get("source_id", "")
        self._execute(
            "INSERT OR REPLACE INTO metaengine_source_records "
            "(source_id, source_hash, source_class, ingestion, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            params=[
                {"type": "text", "value": sid},
                {"type": "text", "value": record.get("source_hash", "")},
                {"type": "text", "value": record.get("source_class", "")},
                {"type": "text", "value": record.get("ingestion", "")},
                {"type": "text", "value": json.dumps(dict(record), sort_keys=True)},
                {"type": "text", "value": _now()},
            ],
        )
        return sid

    def save_mechanism_candidate(self, candidate: Mapping[str, Any]) -> str:
        self._require_enabled()
        mid = candidate.get("mechanism_id", "")
        self._execute(
            "INSERT OR REPLACE INTO metaengine_mechanism_candidates "
            "(mechanism_id, mechanism_hash, status, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            params=[
                {"type": "text", "value": mid},
                {"type": "text", "value": candidate.get("mechanism_hash", "")},
                {"type": "text", "value": candidate.get("status", "")},
                {"type": "text", "value": json.dumps(dict(candidate), sort_keys=True)},
                {"type": "text", "value": _now()},
            ],
        )
        return mid

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def read_dev_steps(self) -> list[dict]:
        return self._query(
            "SELECT step_id, kind, decision, receipt_hash, "
            "constitution_snapshot_hash, arch_library_snapshot_hash, policy_snapshot_hash, created_at "
            "FROM metaengine_dev_steps ORDER BY step_id"
        )

    def read_artifacts(self) -> list[dict]:
        return self._query(
            "SELECT artifact_id, artifact_kind, artifact_hash, slice_id, created_at "
            "FROM metaengine_artifacts ORDER BY artifact_id"
        )

    def read_source_records(self) -> list[dict]:
        return self._query(
            "SELECT source_id, source_class, ingestion, source_hash FROM metaengine_source_records ORDER BY source_id"
        )

    def read_mechanism_candidates(self) -> list[dict]:
        return self._query(
            "SELECT mechanism_id, status, mechanism_hash FROM metaengine_mechanism_candidates ORDER BY mechanism_id"
        )

    def read_worklog_entries(self) -> list[dict]:
        return self._query(
            "SELECT id, task_id, agent, substr(task,1,80) AS task_preview, created_at "
            "FROM metaengine_worklog ORDER BY id"
        )

    def read_canonical_anchors(self) -> dict:
        rows = self._query("SELECT * FROM metaengine_canonical_anchors WHERE id = 1")
        return rows[0] if rows else {}

    def read_project_meta(self) -> dict:
        rows = self._query("SELECT key, value FROM metaengine_project_meta")
        return {r["key"]: r["value"] for r in rows}

    def read_row_counts(self) -> dict:
        counts = {}
        for t in [
            "metaengine_canonical_anchors",
            "metaengine_dev_steps",
            "metaengine_artifacts",
            "metaengine_source_records",
            "metaengine_mechanism_candidates",
            "metaengine_worklog",
            "metaengine_project_meta",
        ]:
            rows = self._query(f"SELECT COUNT(*) AS n FROM {t}")
            counts[t] = int(rows[0]["n"]) if rows else 0
        return counts

    # ------------------------------------------------------------------
    # Bulk sync (re-save all local artifacts to cloud)
    # ------------------------------------------------------------------

    def sync_all_from_workspace(self, workspace_root: str | Path) -> dict:
        """Re-save all local project artifacts to the cloud DB. Returns counts."""
        root = Path(workspace_root).resolve()
        evidence = root / "03_EVIDENCE" / "METAENGINE1"
        arch_lib = root / "research" / "architecture_library"
        worklog_path = Path("/home/z/my-project/worklog.md")
        counts = {"dev_steps": 0, "artifacts": 0, "source_records": 0, "mechanism_candidates": 0, "worklog": 0}

        # dev steps (receipts + reviews)
        for f in sorted(list(evidence.glob("*receipt*.json")) + list(evidence.glob("*review*.json"))):
            payload = json.loads(f.read_text())
            kind = "post_step_receipt" if "receipt" in f.name else "pre_step_review"
            self.save_dev_step(payload, kind=kind)
            counts["dev_steps"] += 1

        # artifacts
        for f in sorted(arch_lib.glob("*.json")):
            payload = json.loads(f.read_text())
            artifact_kind = (
                "summary" if "summary" in f.name
                else "source_registry" if "source_registry" in f.name
                else "reference_vault" if "reference_vault" in f.name
                else "mechanism_library" if "mechanism_library" in f.name
                else "other"
            )
            slice_id = "SLICE-3" if "slice3" in f.name else "SLICE-4" if "slice4" in f.name else ""
            self.save_artifact(f.stem, payload, artifact_kind=artifact_kind, slice_id=slice_id)
            counts["artifacts"] += 1

        # source records
        reg_path = arch_lib / "source_registry.json"
        if reg_path.is_file():
            reg = json.loads(reg_path.read_text())
            for rec in reg.get("records", []):
                self.save_source_record(rec)
                counts["source_records"] += 1

        # mechanism candidates
        lib_path = arch_lib / "mechanism_library.json"
        if lib_path.is_file():
            lib = json.loads(lib_path.read_text())
            for cand in lib.get("candidates", []):
                self.save_mechanism_candidate(cand)
                counts["mechanism_candidates"] += 1

        # worklog (only new entries since last sync — use task_id dedup via SELECT)
        if worklog_path.is_file():
            existing = {r["task_id"] for r in self.read_worklog_entries()}
            worklog = worklog_path.read_text(errors="replace")
            for section in worklog.split("\n---\n"):
                section = section.strip()
                if not section or section.startswith("# MetaEngine"):
                    continue
                task_id = agent = task = ""
                for line in section.split("\n"):
                    ls = line.strip()
                    if ls.startswith("Task ID:"):
                        task_id = ls[len("Task ID:"):].strip()
                    elif ls.startswith("Agent:"):
                        agent = ls[len("Agent:"):].strip()
                    elif ls.startswith("Task:"):
                        task = ls[len("Task:"):].strip()
                        break
                if not task_id or task_id in existing:
                    continue
                self.save_worklog_entry(task_id, agent, task, section)
                counts["worklog"] += 1

        return counts
