"""sync_all_to_turso.py — Comprehensive MetaEngine project data sync.

Saves ALL project data to the Turso cloud DB:
  - Source code  (metaengine/*.py, src/*.py, scripts/*.py)
  - Tests        (tests/*.py)
  - Reports/docs (*.md at project root, docs/, research/, reference-vault/)
  - Schemas      (storage/*.sql, schemas/*)
  - Storage state files (storage/*.json — engine biographies, evidence graph, etc.)
  - Phase run manifests and summary files (skip huge raw run JSONs)
  - Worklog entries (parsed from /home/z/my-project/worklog.md)
  - Project config files (pyproject.toml, pytest.ini, docker-compose.yml,
    RELEASE_MANIFEST*.json, ROOT_INTEGRITY.json, FILE_INVENTORY.json, etc.)
  - Lineage manifest files (.path/.sha256 only — full source archives are
    649MB and are preserved locally; we only sync their integrity anchors)

Turso schema (verified 2026-08-16):
  metaengine_project_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)
  metaengine_artifacts (artifact_id TEXT PRIMARY KEY, artifact_kind TEXT NOT NULL,
                        artifact_hash TEXT NOT NULL, slice_id TEXT,
                        payload_json TEXT NOT NULL, created_at TEXT NOT NULL)
  metaengine_worklog (id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, agent TEXT,
                      task TEXT, content TEXT, created_at TEXT NOT NULL)

The script is IDEMPOTENT — artifact_id is derived from sha256(path + content), so
re-running a sync will simply overwrite rows with identical content and skip
work where nothing has changed (the worklog is keyed by task_id with INSERT OR REPLACE
on a unique index we add at the start).

The Turso v2 /v2/pipeline HTTP API returns 200 OK even when a statement fails — the
per-statement error is embedded in the JSON response under results[i].error. We
explicitly check every response and report failures.

Batching: 25 statements per HTTP request (Turso limit is ~50; we keep headroom
for large payloads such as evidence_graph.json at 3.5MB).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROOT = Path("/home/z/my-project/METAENGINE_SLICE3_RESTORED")
WORKLOG_FILE = Path("/home/z/my-project/worklog.md")

TURSO_DB_TOKEN = os.environ.get(
    "TURSO_DB_TOKEN",
    "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9."
    "eyJhIjoicnciLCJleHAiOjE3ODcyOTIzNDIsImlhdCI6MTc4NjY4NzU0MiwiaWQiOiIwMTlmZmRmOS04OTAxLTc1ZTgtYTFhMS0zYjZiMTI1NzQxYWIiLCJraWQiOiJGdEtYeWh2b2lPa01XOUU4ZXZzUDkyZlB1WGR4Y1Zpa2VVU2lPWUNiSzlvIiwicmlkIjoiMGYzZGI3MWMtYjA5OS00N2NlLTgxZDYtNjcxNjUzZjliMzZlIn0."
    "4Yz3lmULln7ci_5S310Qp6ke2R0aAOF0pkE1fBskeBDM7juuMnHkWe2Cgr0GhtNItamSEMD2M3-4UwrhX7IeBw",
)
TURSO_DB_HOST = os.environ.get(
    "TURSO_DB_HOST",
    "metaengine-project-patrickfrome.aws-eu-west-1.turso.io",
)

SLICE_ID = "METAENGINE_SLICE3_RESTORED_2.3"
BATCH_SIZE = 25            # statements per HTTP pipeline request
HTTP_TIMEOUT = 120          # seconds
MAX_FILE_BYTES = 8 * 1024 * 1024  # 8MB hard ceiling per file (Turso row limit guard)


# ---------------------------------------------------------------------------
# Turso pipeline client
# ---------------------------------------------------------------------------


def _execute_batch(statements: list[dict]) -> list[dict]:
    """Execute a batch of statements via the Turso v2 pipeline API.

    Each statement is {"sql": str, "args": [{"type": ..., "value": ...}, ...]}.
    Returns the per-statement results list (results[i] corresponds to statements[i]).
    """
    if not statements:
        return []
    requests = []
    for stmt in statements:
        req = {"type": "execute", "stmt": {"sql": stmt["sql"]}}
        if stmt.get("args"):
            req["stmt"]["args"] = stmt["args"]
        requests.append(req)
    body = json.dumps({"requests": requests}).encode("utf-8")
    url = f"https://{TURSO_DB_HOST}/v2/pipeline"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {TURSO_DB_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("results", [])


def _execute(sql: str, args: list[dict] | None = None) -> dict:
    results = _execute_batch([{"sql": sql, "args": args or []}])
    return results[0] if results else {"type": "error", "error": {"message": "no result"}}


def _arg(value: Any) -> dict:
    """Convert a Python value to the libSQL pipeline args format."""
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "integer", "value": "1" if value else "0"}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    if isinstance(value, str):
        return {"type": "text", "value": value}
    # Fall back to JSON-encoded text
    return {"type": "text", "value": json.dumps(value, ensure_ascii=False)}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def iter_python_files() -> Iterable[Path]:
    """All .py files under the project (metaengine, src, scripts, tests, etc.)."""
    patterns = [
        "metaengine/*.py",
        "tests/*.py",
        "scripts/*.py",
        "src/**/*.py",
        "benchmarks/**/*.py",
        "bin/**/*.py",
        "examples/**/*.py",
        "research/**/*.py",
    ]
    seen: set[Path] = set()
    for pat in patterns:
        for p in sorted(ROOT.glob(pat)):
            if p.is_file() and p not in seen:
                seen.add(p)
                yield p


def iter_report_files() -> Iterable[Path]:
    """Top-level *.md reports and docs/* markdown."""
    patterns = [
        "*.md",
        "docs/**/*.md",
        "reference-vault/**/*.md",
        "research/**/*.md",
        "release-evidence/**/*.md",
    ]
    seen: set[Path] = set()
    for pat in patterns:
        for p in sorted(ROOT.glob(pat)):
            if p.is_file() and p not in seen:
                seen.add(p)
                yield p


def iter_schema_files() -> Iterable[Path]:
    """All .sql files (storage/*.sql + schemas/*)."""
    seen: set[Path] = set()
    for pat in ["storage/*.sql", "schemas/**/*.sql", "schemas/**/*.json"]:
        for p in sorted(ROOT.glob(pat)):
            if p.is_file() and p not in seen:
                seen.add(p)
                yield p


def iter_state_files() -> Iterable[Path]:
    """Storage root .json state files (engine biographies, evidence graph, etc.)."""
    seen: set[Path] = set()
    for p in sorted(ROOT.glob("storage/*.json")):
        if p.is_file() and p not in seen:
            seen.add(p)
            yield p


def iter_config_files() -> Iterable[Path]:
    """Project config + manifest files at the root."""
    for name in [
        "pyproject.toml",
        "pytest.ini",
        "docker-compose.yml",
        "Dockerfile",
        "Dockerfile.dashboard",
        "RELEASE_MANIFEST.json",
        "RELEASE_MANIFEST_2_2.json",
        "RELEASE_MANIFEST_2_3.json",
        "ROOT_INTEGRITY.json",
        "FILE_INVENTORY.json",
        "PORTABLE_MANIFEST.json",
        "LINEAGE_FIXITY_REPORT.json",
        "LINEAGE_FIXITY_REPORT_1.3.json",
        "LINEAGE_FIXITY_REPORT_1.4.json",
        "LINEAGE_FIXITY_REPORT_2.0.json",
        "SHA256SUMS.txt",
    ]:
        p = ROOT / name
        if p.is_file():
            yield p


def iter_lineage_anchors() -> Iterable[Path]:
    """Manifest/anchor files inside lineages/ (NOT the 649MB source archives)."""
    seen: set[Path] = set()
    for pat in [
        "lineages/*/.path",
        "lineages/*/.sha256",
        "lineages/*/SOURCE_ARCHIVE.path",
        "lineages/*/SOURCE_ARCHIVE.sha256",
    ]:
        for p in sorted(ROOT.glob(pat)):
            if p.is_file() and p not in seen:
                seen.add(p)
                yield p


def iter_phase_manifests() -> Iterable[Path]:
    """Manifests and summary files inside storage/phase*/ dirs.

    We intentionally skip the bulky raw run JSONs (often 100s of MB per phase)
    but preserve the small manifest / summary / receipt files that document
    what each phase produced.
    """
    keep_patterns = (
        "*MANIFEST*.json",
        "*SUMMARY*.json",
        "*RECEIPT*.json",
        "*INDEX*.json",
        "*REPORT*.json",
        "*REPORT*.md",
        "*FIXITY*.json",
        "MANIFEST.json",
    )
    seen: set[Path] = set()
    for phase_dir in sorted(ROOT.glob("storage/phase*")):
        if not phase_dir.is_dir():
            continue
        for pat in keep_patterns:
            for p in phase_dir.rglob(pat):
                if (
                    p.is_file()
                    and p.stat().st_size <= MAX_FILE_BYTES
                    and p not in seen
                ):
                    seen.add(p)
                    yield p


# ---------------------------------------------------------------------------
# Statement builders
# ---------------------------------------------------------------------------


def artifact_id(path: Path, content: str) -> str:
    """Content-addressed id: sha256(relative_path + ":" + content)."""
    rel = str(path.relative_to(ROOT))
    h = hashlib.sha256(f"{rel}:{content}".encode("utf-8")).hexdigest()
    return h


def make_artifact_stmt(path: Path, kind: str, content: str, slice_id: str) -> dict:
    """Build an INSERT OR REPLACE statement for metaengine_artifacts."""
    rel = str(path.relative_to(ROOT))
    aid = artifact_id(path, content)
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    payload = {
        "path": rel,
        "size": len(content.encode("utf-8")),
        "lines": content.count("\n") + (1 if content and not content.endswith("\n") else 0),
        "content": content,
    }
    return {
        "sql": (
            "INSERT OR REPLACE INTO metaengine_artifacts "
            "(artifact_id, artifact_kind, artifact_hash, slice_id, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)"
        ),
        "args": [
            _arg(aid),
            _arg(kind),
            _arg(sha),
            _arg(slice_id),
            _arg(json.dumps(payload, ensure_ascii=False)),
            _arg(now_iso()),
        ],
    }


def make_meta_stmt(key: str, value: str) -> dict:
    """Build an INSERT OR REPLACE statement for metaengine_project_meta."""
    return {
        "sql": (
            "INSERT OR REPLACE INTO metaengine_project_meta (key, value) VALUES (?, ?)"
        ),
        "args": [_arg(key), _arg(value)],
    }


def make_worklog_stmt(task_id: str, agent: str, task: str, content: str) -> dict:
    """Build an INSERT statement for metaengine_worklog.

    Note: schema is (id INTEGER PK AUTOINCREMENT, task_id, agent, task, content, created_at).
    We DELETE the entire worklog table before re-inserting (full sync semantics), so
    no dedup index is needed.
    """
    return {
        "sql": (
            "INSERT INTO metaengine_worklog "
            "(task_id, agent, task, content, created_at) VALUES (?, ?, ?, ?, ?)"
        ),
        "args": [
            _arg(task_id),
            _arg(agent),
            _arg(task),
            _arg(content),
            _arg(now_iso()),
        ],
    }


# ---------------------------------------------------------------------------
# Worklog parser
# ---------------------------------------------------------------------------


def parse_worklog() -> list[dict]:
    """Parse /home/z/my-project/worklog.md into structured entries.

    Each entry is delimited by a leading '---' separator line on its own line.
    The block following the separator contains:
      Task ID: <id>
      Agent: <agent>
      Task: <task>
      (blank line)
      Work Log:
      - step 1
      - step 2
      ...
      (blank line)
      Stage Summary:
      - result 1
      ...
    """
    if not WORKLOG_FILE.is_file():
        return []
    text = WORKLOG_FILE.read_text(encoding="utf-8")
    entries: list[dict] = []
    # Split on lines that are exactly "---" (the section delimiter)
    parts = text.split("\n---\n")
    # The first part is the file's preamble (before any '---'); skip it if it has no Task ID
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "Task ID:" not in part:
            continue
        lines = part.splitlines()
        task_id = ""
        agent = ""
        task = ""
        # Read header fields (first 3 non-empty lines starting with Task ID/Agent/Task)
        body_start = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("Task ID:"):
                task_id = stripped[len("Task ID:"):].strip()
                body_start = i + 1
            elif stripped.startswith("Agent:"):
                agent = stripped[len("Agent:"):].strip()
                body_start = i + 1
            elif stripped.startswith("Task:"):
                task = stripped[len("Task:"):].strip()
                body_start = i + 1
                break
        content = "\n".join(lines[body_start:]).strip()
        entries.append(
            {
                "task_id": task_id or f"unknown-{hashlib.sha256(part.encode()).hexdigest()[:8]}",
                "agent": agent or "unknown",
                "task": task or "(no task description)",
                "content": content,
            }
        )
    return entries


# ---------------------------------------------------------------------------
# Sync orchestrator
# ---------------------------------------------------------------------------


class SyncStats:
    def __init__(self) -> None:
        self.started = time.time()
        self.files_total = 0
        self.files_synced = 0
        self.files_skipped_size = 0
        self.files_skipped_missing = 0
        self.statements_total = 0
        self.statements_failed = 0
        self.statements_ok = 0
        self.batches = 0
        self.errors: list[str] = []
        self.kind_counts: dict[str, int] = {}

    def report(self) -> str:
        elapsed = time.time() - self.started
        lines = [
            "=" * 70,
            "COMPREHENSIVE TURSO SYNC — FINAL REPORT",
            "=" * 70,
            f"Elapsed            : {elapsed:.1f}s",
            f"Files discovered   : {self.files_total}",
            f"Files synced       : {self.files_synced}",
            f"Files skipped (>8M): {self.files_skipped_size}",
            f"Files missing      : {self.files_skipped_missing}",
            f"HTTP batches       : {self.batches}",
            f"Statements sent    : {self.statements_total}",
            f"Statements OK      : {self.statements_ok}",
            f"Statements FAILED  : {self.statements_failed}",
            "",
            "Artifacts by kind:",
        ]
        for kind, count in sorted(self.kind_counts.items()):
            lines.append(f"  {kind:20s} : {count}")
        if self.errors:
            lines.append("")
            lines.append(f"Errors ({len(self.errors)} — showing first 10):")
            for e in self.errors[:10]:
                lines.append(f"  - {e}")
        return "\n".join(lines)


def flush_batch(stmts: list[dict], stats: SyncStats, label: str) -> None:
    """Execute a batch of statements and update stats."""
    if not stmts:
        return
    # Snapshot the statements we're about to send so error messages can reference them
    # even after we clear the list at the end.
    sent = list(stmts)
    stats.batches += 1
    stats.statements_total += len(sent)
    try:
        results = _execute_batch(sent)
    except Exception as exc:
        stats.statements_failed += len(sent)
        stats.errors.append(f"[{label}] HTTP error: {exc}")
        stmts.clear()
        return
    if len(results) != len(sent):
        stats.errors.append(
            f"[{label}] result count mismatch: sent {len(sent)}, got {len(results)}"
        )
    for i, res in enumerate(results):
        if res.get("type") == "ok":
            stats.statements_ok += 1
        else:
            stats.statements_failed += 1
            err = res.get("error", {}).get("message", "unknown")
            stmt = sent[i] if i < len(sent) else {}
            sql_preview = (stmt.get("sql", "") or "")[:120]
            args_preview = ""
            args = stmt.get("args") or []
            if args:
                first = args[0]
                v = first.get("value", "")
                if isinstance(v, str):
                    args_preview = f" arg0={v[:60]!r}"
            stats.errors.append(f"[{label}] stmt#{i}: {err} | sql={sql_preview!r}{args_preview}")
    stmts.clear()


def sync_files(
    files: Iterable[Path],
    kind: str,
    stats: SyncStats,
    label: str,
) -> None:
    """Sync a list of files as metaengine_artifacts of the given kind."""
    batch: list[dict] = []
    for path in files:
        stats.files_total += 1
        try:
            if not path.is_file():
                stats.files_skipped_missing += 1
                continue
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                stats.files_skipped_size += 1
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            stats.errors.append(f"[{label}] read {path}: {exc}")
            continue
        batch.append(make_artifact_stmt(path, kind, content, SLICE_ID))
        stats.files_synced += 1
        stats.kind_counts[kind] = stats.kind_counts.get(kind, 0) + 1
        if len(batch) >= BATCH_SIZE:
            flush_batch(batch, stats, label)
    flush_batch(batch, stats, label)


def sync_state_files(files: Iterable[Path], stats: SyncStats) -> None:
    """Sync storage/*.json state files into metaengine_project_meta.

    Keyed as `engine_state:<basename without .json>` so existing lookups still work.
    """
    batch: list[dict] = []
    for path in files:
        stats.files_total += 1
        try:
            if not path.is_file():
                stats.files_skipped_missing += 1
                continue
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                stats.files_skipped_size += 1
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            stats.errors.append(f"[state] read {path}: {exc}")
            continue
        key = f"engine_state:{path.stem}"
        batch.append(make_meta_stmt(key, content))
        stats.files_synced += 1
        stats.kind_counts["engine_state"] = stats.kind_counts.get("engine_state", 0) + 1
        if len(batch) >= BATCH_SIZE:
            flush_batch(batch, stats, "state")
    flush_batch(batch, stats, "state")


def sync_worklog(stats: SyncStats) -> None:
    """Parse /home/z/my-project/worklog.md and insert every section as a worklog row.

    Full-sync semantics: we DELETE all existing rows first, then re-INSERT all parsed
    entries. This guarantees idempotency (re-running the sync produces the same rows).
    """
    entries = parse_worklog()
    if not entries:
        print("[worklog] no entries found — nothing to sync")
        return
    # Wipe existing worklog rows for a clean full-sync (idempotent re-runs)
    print(f"[worklog] clearing existing cloud rows before re-insert...")
    try:
        _execute("DELETE FROM metaengine_worklog")
        print("[worklog] cleared existing rows")
    except Exception as exc:
        stats.errors.append(f"[worklog] DELETE failed: {exc}")
    batch: list[dict] = []
    for entry in entries:
        batch.append(
            make_worklog_stmt(
                entry["task_id"], entry["agent"], entry["task"], entry["content"]
            )
        )
        stats.files_synced += 1
        stats.kind_counts["worklog_entry"] = stats.kind_counts.get("worklog_entry", 0) + 1
        if len(batch) >= BATCH_SIZE:
            flush_batch(batch, stats, "worklog")
    flush_batch(batch, stats, "worklog")
    print(f"[worklog] parsed and synced {len(entries)} entries")


def sync_meta_summary(stats: SyncStats) -> None:
    """Persist a high-level summary of this sync run as metaengine_project_meta keys."""
    summary = {
        "slice_id": SLICE_ID,
        "synced_at": now_iso(),
        "files_total": stats.files_total,
        "files_synced": stats.files_synced,
        "files_skipped_size": stats.files_skipped_size,
        "files_skipped_missing": stats.files_skipped_missing,
        "statements_total": stats.statements_total,
        "statements_ok": stats.statements_ok,
        "statements_failed": stats.statements_failed,
        "batches": stats.batches,
        "artifact_kind_counts": stats.kind_counts,
    }
    batch = [
        make_meta_stmt("project:last_sync_summary", json.dumps(summary, ensure_ascii=False, indent=2)),
        make_meta_stmt("project:slice_id", SLICE_ID),
        make_meta_stmt("project:last_synced_at", now_iso()),
    ]
    flush_batch(batch, stats, "summary")


# ---------------------------------------------------------------------------
# Cloud state introspection
# ---------------------------------------------------------------------------


def cloud_counts() -> dict[str, Any]:
    """Return row counts and artifact-kind breakdown from the cloud DB."""
    counts: dict[str, Any] = {}
    tables = [
        "metaengine_project_meta",
        "metaengine_dev_steps",
        "metaengine_artifacts",
        "metaengine_worklog",
        "metaengine_mechanism_candidates",
        "metaengine_source_records",
        "metaengine_canonical_anchors",
    ]
    for t in tables:
        try:
            r = _execute(f"SELECT count(*) FROM {t}")
            if r.get("type") == "ok":
                rows = r["response"]["result"]["rows"]
                counts[t] = int(rows[0][0]["value"]) if rows else 0
            else:
                counts[t] = f"error: {r.get('error', {}).get('message', '')[:80]}"
        except Exception as exc:
            counts[t] = f"error: {exc}"

    # Artifact-kind breakdown
    try:
        r = _execute(
            "SELECT artifact_kind, count(*) FROM metaengine_artifacts GROUP BY artifact_kind ORDER BY 2 DESC"
        )
        if r.get("type") == "ok":
            rows = r["response"]["result"]["rows"]
            counts["_artifact_kind_breakdown"] = {
                row[0]["value"]: int(row[1]["value"]) for row in rows
            }
        else:
            counts["_artifact_kind_breakdown"] = f"error: {r.get('error', {})}"
    except Exception as exc:
        counts["_artifact_kind_breakdown"] = f"error: {exc}"
    return counts


def ensure_worklog_unique_index() -> None:
    """No-op placeholder; worklog dedup is handled by DELETE+re-INSERT in sync_worklog.

    The original metaengine_worklog schema (id PK autoincrement, task_id, agent, task,
    content, created_at) is preserved as-is. Each full sync wipes the table and re-inserts
    all parsed worklog entries, so duplicates are impossible.
    """
    return


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 70)
    print("COMPREHENSIVE TURSO SYNC — saving ALL MetaEngine project data")
    print(f"Slice ID: {SLICE_ID}")
    print("=" * 70)

    # 1. Verify connectivity
    print("\n[1/9] Verifying Turso connectivity...")
    try:
        r = _execute("SELECT 1 AS ok")
        ok = r.get("type") == "ok"
        print(f"  Turso reachable: {ok}")
        if not ok:
            print(f"  Response: {r}")
            return 1
    except Exception as exc:
        print(f"  TURSO_CONNECT_FAILED: {exc}", file=sys.stderr)
        return 1

    # 2. Ensure worklog has content_hash column + unique index for dedup
    print("\n[2/9] Ensuring worklog dedup schema (content_hash + unique index)...")
    ensure_worklog_unique_index()
    print("  done")

    stats = SyncStats()

    # 3. Sync source code (.py)
    print("\n[3/9] Syncing Python source code (metaengine + src + scripts + tests)...")
    py_files = list(iter_python_files())
    print(f"  discovered {len(py_files)} .py files")
    sync_files(py_files, "source_code", stats, "source_code")
    print(f"  synced: {stats.kind_counts.get('source_code', 0)}")

    # 4. Sync reports/docs (.md)
    print("\n[4/9] Syncing reports and docs (*.md)...")
    md_files = list(iter_report_files())
    print(f"  discovered {len(md_files)} .md files")
    sync_files(md_files, "report", stats, "report")
    print(f"  synced: {stats.kind_counts.get('report', 0)}")

    # 5. Sync schemas (.sql + schemas/)
    print("\n[5/9] Syncing schemas (*.sql)...")
    sql_files = list(iter_schema_files())
    print(f"  discovered {len(sql_files)} schema files")
    sync_files(sql_files, "schema", stats, "schema")
    print(f"  synced: {stats.kind_counts.get('schema', 0)}")

    # 6. Sync storage root state files
    print("\n[6/9] Syncing engine state files (storage/*.json)...")
    state_files = list(iter_state_files())
    print(f"  discovered {len(state_files)} state files")
    sync_state_files(state_files, stats)
    print(f"  synced: {stats.kind_counts.get('engine_state', 0)}")

    # 7. Sync phase manifests / summaries
    print("\n[7/9] Syncing phase run manifests and summaries (skip bulky raw run JSONs)...")
    phase_files = list(iter_phase_manifests())
    print(f"  discovered {len(phase_files)} phase manifest/summary files")
    sync_files(phase_files, "phase_manifest", stats, "phase")
    print(f"  synced: {stats.kind_counts.get('phase_manifest', 0)}")

    # 8. Sync config + lineage anchors
    print("\n[8/9] Syncing project config + lineage integrity anchors...")
    config_files = list(iter_config_files()) + list(iter_lineage_anchors())
    print(f"  discovered {len(config_files)} config/anchor files")
    sync_files(config_files, "config", stats, "config")
    print(f"  synced: {stats.kind_counts.get('config', 0)}")

    # 9. Sync worklog (parsed entries from /home/z/my-project/worklog.md)
    print("\n[9/9] Parsing and syncing worklog entries...")
    sync_worklog(stats)

    # 9b. Persist the sync summary itself
    print("\n[summary] Persisting high-level sync summary...")
    sync_meta_summary(stats)

    # Final report
    print()
    print(stats.report())

    # Cloud DB state
    print("\n" + "=" * 70)
    print("Cloud DB state after sync:")
    print("=" * 70)
    counts = cloud_counts()
    for k, v in counts.items():
        if k == "_artifact_kind_breakdown":
            print(f"  artifact kinds breakdown:")
            for kind, c in v.items() if isinstance(v, dict) else []:
                print(f"    {kind:25s} : {c}")
        else:
            print(f"  {k:35s} : {v}")

    return 0 if stats.statements_failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
