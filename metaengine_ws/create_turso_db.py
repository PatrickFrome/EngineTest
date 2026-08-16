#!/usr/bin/env python3
"""METAENGINE — create a Turso libSQL cloud DB and migrate the full project state.

Creates a new Turso group + database, applies a focused project-state schema
(libSQL/SQLite-compatible), and migrates all existing MetaEngine project
artifacts (canonical anchors, development receipts, architecture-library
artifacts, source records, mechanism candidates, worklog).

Security: the Turso API token and the generated DB auth token are read from
the environment ONLY. They are never written to any file, log, or artifact.
The creation record stores only non-secret metadata (db name, host, urls).

Required env (inject via trusted runtime, NEVER persist in the project):
    TURSO_API_TOKEN  -- Turso platform API token

The DB access token is generated at runtime and returned to the caller via
stdout (so the user can save it in their secret manager); it is NOT written
to disk by this script.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.turso.tech"
ROOT = Path(__file__).resolve().parent
LOCATION = "aws-eu-west-1"  # AWS EU West (Ireland) — closest valid Turso region to Europe/Moscow
GROUP_NAME = "metaengine"
DB_NAME = "metaengine-project"
EVIDENCE = ROOT / "03_EVIDENCE" / "METAENGINE1"
ARCH_LIB = ROOT / "research" / "architecture_library"

# ---------------------------------------------------------------------------
# Turso platform API client
# ---------------------------------------------------------------------------


def _platform(method: str, path: str, *, token: str, body: dict | None = None) -> dict:
    url = API + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = resp.read().decode("utf-8")
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8")
        raise SystemExit(f"TURSO_API_ERROR {method} {path}: HTTP {exc.code}\n{body_text}") from exc


def ensure_group(token: str) -> dict:
    groups = _platform("GET", "/v1/groups", token=token).get("groups", [])
    for g in groups:
        if g["name"] == GROUP_NAME:
            print(f"[group] reuse existing: {GROUP_NAME} ({g.get('location','?')})")
            return g
    print(f"[group] creating: {GROUP_NAME} in {LOCATION}")
    return _platform("POST", "/v1/groups", token=token, body={"name": GROUP_NAME, "location": LOCATION})


def create_database(token: str) -> dict:
    # Check if DB already exists first (reuse on 409/400-duplicate)
    dbs = _platform("GET", "/v1/databases", token=token).get("databases", [])
    for d in dbs:
        if d.get("Name") == DB_NAME:
            print(f"[db] reuse existing: {DB_NAME} (host={d.get('Hostname')})")
            return {"database": d}
    print(f"[db] creating: {DB_NAME} in group {GROUP_NAME}")
    return _platform("POST", "/v1/databases", token=token, body={"group": GROUP_NAME, "name": DB_NAME})


def wait_db_ready(token: str, db_name: str, timeout: float = 120.0) -> dict:
    # Fetch the full DB list and find ours; the single-DB GET returns a different shape.
    deadline = time.time() + timeout
    while time.time() < deadline:
        dbs = _platform("GET", "/v1/databases", token=token).get("databases", [])
        for d in dbs:
            if d.get("Name") == db_name and d.get("Hostname"):
                return {"Hostname": d["Hostname"], "OrgID": d.get("OrgID", "")}
        time.sleep(3)
    raise SystemExit(f"TIMEOUT waiting for db {db_name}")


def create_db_token(token: str, db_name: str) -> str:
    """Create a DB-level auth token. Returned to caller; never persisted."""
    print(f"[token] creating DB access token for {db_name}")
    result = _platform("POST", f"/v1/databases/{db_name}/auth/tokens", token=token, body={})
    return result["jwt"]


# ---------------------------------------------------------------------------
# libSQL HTTP pipeline client (apply SQL to the DB)
# ---------------------------------------------------------------------------


def libsql_execute(host: str, db_token: str, sql: str, *, params: list | None = None) -> dict:
    """Execute SQL via the libSQL v2 pipeline HTTP API."""
    url = f"https://{host}/v2/pipeline"
    req_body = {
        "requests": [
            {
                "type": "execute",
                "stmt": {"sql": sql, **({"args": params} if params else {})},
            }
        ]
    }
    data = json.dumps(req_body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {db_token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise SystemExit(f"LIBSQL_ERROR: HTTP {exc.code}\nSQL: {sql[:200]}\n{body}") from exc


def libsql_query(host: str, db_token: str, sql: str) -> list[dict]:
    """Query and return rows as dicts."""
    result = libsql_execute(host, db_token, sql)
    try:
        res = result["results"][0]["response"]
        if "result" in res and res["result"]["type"] == "ok":
            # SELECT returns rows
            rows = res.get("result", {}).get("rows", [])
            cols = result["results"][0]["response"]["result"].get("cols", [])
            col_names = [c.get("name", f"c{i}") for i, c in enumerate(cols)]
            out = []
            for row in rows:
                values = []
                for v in row.get("values", []):
                    if "type" in v:
                        if v["type"] == "null":
                            values.append(None)
                        elif v["type"] in ("integer", "text", "float"):
                            values.append(v["value"])
                        else:
                            values.append(v.get("value"))
                    else:
                        values.append(None)
                out.append(dict(zip(col_names, values)))
            return out
    except (KeyError, IndexError, TypeError):
        pass
    return []


# ---------------------------------------------------------------------------
# Schema (libSQL/SQLite-compatible project-state schema)
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS metaengine_canonical_anchors (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  checkpoint_id TEXT NOT NULL,
  checkpoint_status TEXT NOT NULL,
  checkpoint_current INTEGER NOT NULL,
  active_policy_hash TEXT NOT NULL,
  champion_generation INTEGER NOT NULL,
  captured_at TEXT NOT NULL,
  source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metaengine_dev_steps (
  step_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  receipt_hash TEXT,
  decision TEXT,
  constitution_snapshot_hash TEXT,
  arch_library_snapshot_hash TEXT,
  policy_snapshot_hash TEXT,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metaengine_artifacts (
  artifact_id TEXT PRIMARY KEY,
  artifact_kind TEXT NOT NULL,
  artifact_hash TEXT NOT NULL,
  slice_id TEXT,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metaengine_source_records (
  source_id TEXT PRIMARY KEY,
  source_hash TEXT NOT NULL,
  source_class TEXT NOT NULL,
  ingestion TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metaengine_mechanism_candidates (
  mechanism_id TEXT PRIMARY KEY,
  mechanism_hash TEXT NOT NULL,
  status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metaengine_worklog (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL,
  agent TEXT NOT NULL,
  task TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metaengine_project_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


def apply_schema(host: str, db_token: str) -> None:
    print("[schema] applying project-state schema to libSQL DB...")
    # Execute each statement separately (pipeline API handles one stmt per request)
    statements = [s.strip() for s in SCHEMA_SQL.split(";") if s.strip()]
    for stmt in statements:
        libsql_execute(host, db_token, stmt)
    print(f"[schema] applied {len(statements)} statements")


# ---------------------------------------------------------------------------
# Migrate existing project artifacts
# ---------------------------------------------------------------------------


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def migrate_canonical_anchors(host: str, db_token: str) -> None:
    readback = json.loads((EVIDENCE / "current_canonical_readback.json").read_text())
    cp = readback["checkpoint"]
    ap = readback["active_policy"]
    libsql_execute(
        host, db_token,
        "INSERT OR REPLACE INTO metaengine_canonical_anchors "
        "(id, checkpoint_id, checkpoint_status, checkpoint_current, active_policy_hash, champion_generation, captured_at, source) "
        "VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
        params=[
            {"type": "text", "value": cp["checkpoint_id"]},
            {"type": "text", "value": cp["verification_status"]},
            {"type": "integer", "value": "1" if cp["is_current"] else "0"},
            {"type": "text", "value": ap["policy_hash"]},
            {"type": "integer", "value": str(ap["generation"])},
            {"type": "text", "value": readback.get("captured_at", _now())},
            {"type": "text", "value": "bundled LIVE_CANONICAL_READBACK.json (point-in-time)"},
        ],
    )
    print("[migrate] canonical_anchors: 1 row")


def migrate_receipts(host: str, db_token: str) -> None:
    receipt_files = sorted(EVIDENCE.glob("*receipt*.json")) + sorted(EVIDENCE.glob("*review*.json"))
    count = 0
    for f in receipt_files:
        payload = json.loads(f.read_text())
        step_id = payload.get("step_id") or payload.get("completed_step_id") or f.stem
        kind = "post_step_receipt" if "receipt" in f.name else "pre_step_review"
        receipt_hash = payload.get("receipt_hash", "")
        decision = payload.get("decision", "")
        libsql_execute(
            host, db_token,
            "INSERT OR REPLACE INTO metaengine_dev_steps "
            "(step_id, kind, receipt_hash, decision, constitution_snapshot_hash, arch_library_snapshot_hash, policy_snapshot_hash, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            params=[
                {"type": "text", "value": f"{step_id}:{kind}"},
                {"type": "text", "value": kind},
                {"type": "text", "value": receipt_hash},
                {"type": "text", "value": str(decision)},
                {"type": "text", "value": payload.get("constitution_hash") or payload.get("constitution_snapshot_hash", "")},
                {"type": "text", "value": payload.get("architecture_library_snapshot_hash", "")},
                {"type": "text", "value": payload.get("policy_snapshot_hash", "")},
                {"type": "text", "value": json.dumps(payload, sort_keys=True)},
                {"type": "text", "value": _now()},
            ],
        )
        count += 1
    print(f"[migrate] dev_steps (receipts/reviews): {count} rows")


def migrate_artifacts(host: str, db_token: str) -> None:
    count = 0
    for f in sorted(ARCH_LIB.glob("*.json")):
        payload = json.loads(f.read_text())
        artifact_id = f.stem
        artifact_kind = "summary" if "summary" in f.name else (
            "source_registry" if "source_registry" in f.name else
            "reference_vault" if "reference_vault" in f.name else
            "mechanism_library" if "mechanism_library" in f.name else "other"
        )
        artifact_hash = (
            payload.get("registry_hash") or payload.get("vault_hash") or
            payload.get("library_hash") or payload.get("mechanism_library_hash") or ""
        )
        slice_id = "SLICE-3" if "slice3" in f.name else "SLICE-4" if "slice4" in f.name else ""
        libsql_execute(
            host, db_token,
            "INSERT OR REPLACE INTO metaengine_artifacts "
            "(artifact_id, artifact_kind, artifact_hash, slice_id, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            params=[
                {"type": "text", "value": artifact_id},
                {"type": "text", "value": artifact_kind},
                {"type": "text", "value": artifact_hash},
                {"type": "text", "value": slice_id},
                {"type": "text", "value": json.dumps(payload, sort_keys=True)},
                {"type": "text", "value": _now()},
            ],
        )
        count += 1
    print(f"[migrate] artifacts: {count} rows")


def migrate_source_records(host: str, db_token: str) -> None:
    reg = json.loads((ARCH_LIB / "source_registry.json").read_text())
    count = 0
    for rec in reg.get("records", []):
        libsql_execute(
            host, db_token,
            "INSERT OR REPLACE INTO metaengine_source_records "
            "(source_id, source_hash, source_class, ingestion, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            params=[
                {"type": "text", "value": rec["source_id"]},
                {"type": "text", "value": rec.get("source_hash", "")},
                {"type": "text", "value": rec.get("source_class", "")},
                {"type": "text", "value": rec.get("ingestion", "")},
                {"type": "text", "value": json.dumps(rec, sort_keys=True)},
                {"type": "text", "value": _now()},
            ],
        )
        count += 1
    print(f"[migrate] source_records: {count} rows")


def migrate_mechanism_candidates(host: str, db_token: str) -> None:
    lib = json.loads((ARCH_LIB / "mechanism_library.json").read_text())
    count = 0
    for cand in lib.get("candidates", []):
        libsql_execute(
            host, db_token,
            "INSERT OR REPLACE INTO metaengine_mechanism_candidates "
            "(mechanism_id, mechanism_hash, status, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            params=[
                {"type": "text", "value": cand["mechanism_id"]},
                {"type": "text", "value": cand.get("mechanism_hash", "")},
                {"type": "text", "value": cand.get("status", "")},
                {"type": "text", "value": json.dumps(cand, sort_keys=True)},
                {"type": "text", "value": _now()},
            ],
        )
        count += 1
    print(f"[migrate] mechanism_candidates: {count} rows")


def migrate_worklog(host: str, db_token: str) -> None:
    worklog = (Path("/home/z/my-project/worklog.md")).read_text(errors="replace")
    # Split into sections by '---' boundaries
    sections = worklog.split("\n---\n")
    count = 0
    for section in sections:
        section = section.strip()
        if not section or section.startswith("# MetaEngine"):
            continue
        # Extract Task ID / Agent / Task from the section
        task_id = ""
        agent = ""
        task = ""
        for line in section.split("\n"):
            ls = line.strip()
            if ls.startswith("Task ID:"):
                task_id = ls[len("Task ID:"):].strip()
            elif ls.startswith("Agent:"):
                agent = ls[len("Agent:"):].strip()
            elif ls.startswith("Task:"):
                task = ls[len("Task:"):].strip()
                break
        if not task_id:
            continue
        libsql_execute(
            host, db_token,
            "INSERT INTO metaengine_worklog (task_id, agent, task, content, created_at) VALUES (?, ?, ?, ?, ?)",
            params=[
                {"type": "text", "value": task_id},
                {"type": "text", "value": agent},
                {"type": "text", "value": task[:500]},
                {"type": "text", "value": section},
                {"type": "text", "value": _now()},
            ],
        )
        count += 1
    print(f"[migrate] worklog: {count} entries")


def set_project_meta(host: str, db_token: str) -> None:
    meta = {
        "project": "MetaEngine / Destruktion 4.0 METAENGINE 16X",
        "program": "METAENGINE-1 Constitutional Kernel & Architectural Assimilation Foundation",
        "portable_git_head": "637d0b569e38c2a965b43f7de2015ea66a788428",
        "canonical_checkpoint": "metaengine-chat-2.3.0-alpha.1-cp001",
        "active_policy_hash": "1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48",
        "cloud_store_kind": "TURSO_LIBSQL_CLOUD_DB",
        "cloud_store_role": "NON_CANONICAL_PROJECT_STATE_PERSISTENCE",
        "canonical_authority": "false",
        "created_at": _now(),
    }
    for k, v in meta.items():
        libsql_execute(
            host, db_token,
            "INSERT OR REPLACE INTO metaengine_project_meta (key, value) VALUES (?, ?)",
            params=[{"type": "text", "value": k}, {"type": "text", "value": v}],
        )
    print(f"[meta] project_meta: {len(meta)} rows")


def verify(host: str, db_token: str) -> dict:
    counts = {}
    for table in ["metaengine_canonical_anchors", "metaengine_dev_steps", "metaengine_artifacts",
                  "metaengine_source_records", "metaengine_mechanism_candidates",
                  "metaengine_worklog", "metaengine_project_meta"]:
        rows = libsql_query(host, db_token, f"SELECT COUNT(*) AS n FROM {table}")
        counts[table] = rows[0].get("n", "?") if rows else "?"
    return counts


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    token = os.environ.get("TURSO_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("TURSO_API_TOKEN is not set in the environment.")
    print("=== TURSO CLOUD DB CREATION ===")
    ensure_group(token)
    create_database(token)
    info = wait_db_ready(token, DB_NAME)
    host = info["Hostname"]
    print(f"[db] ready: host={host}")
    db_token = create_db_token(token, DB_NAME)

    print("\n=== APPLY SCHEMA ===")
    apply_schema(host, db_token)

    print("\n=== MIGRATE PROJECT STATE ===")
    set_project_meta(host, db_token)
    migrate_canonical_anchors(host, db_token)
    migrate_receipts(host, db_token)
    migrate_artifacts(host, db_token)
    migrate_source_records(host, db_token)
    migrate_mechanism_candidates(host, db_token)
    migrate_worklog(host, db_token)

    print("\n=== VERIFY ===")
    counts = verify(host, db_token)
    print(json.dumps(counts, indent=2))

    # Write creation record WITHOUT any tokens
    record = {
        "status": "CLOUD_DB_CREATED",
        "store_kind": "TURSO_LIBSQL_CLOUD_DB",
        "canonical_authority": False,
        "role": "NON_CANONICAL_PROJECT_STATE_PERSISTENCE",
        "provider": "turso",
        "group": GROUP_NAME,
        "database": DB_NAME,
        "host": host,
        "libsql_url": f"libsql://{host}",
        "https_url": f"https://{host}",
        "dashboard_url": f"https://app.turso.tech/app/orgs/{info.get('OrgID','')}/databases/{DB_NAME}",
        "location": LOCATION,
        "row_counts": counts,
        "schema_tables": [
            "metaengine_canonical_anchors",
            "metaengine_dev_steps",
            "metaengine_artifacts",
            "metaengine_source_records",
            "metaengine_mechanism_candidates",
            "metaengine_worklog",
            "metaengine_project_meta",
        ],
        "note": "DB auth token was printed to stdout only (not persisted). Store it in your secret manager as TURSO_DB_TOKEN for the persister.",
    }
    out = EVIDENCE / "cloud_db_creation_record.json"
    out.write_text(json.dumps(record, indent=2))
    print(f"\n[record] written to {out}")

    print("\n=== DB ACCESS TOKEN (SAVE THIS, NOT RECORDED) ===")
    print(f"TURSO_DB_TOKEN={db_token}")
    print(f"\nlibsql URL: libsql://{host}")
    print(f"HTTPS URL: https://{host}")
    print("\nCLOUD_DB_CREATE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
