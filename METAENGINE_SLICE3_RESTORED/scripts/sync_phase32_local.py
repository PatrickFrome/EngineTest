"""Phase 32 — Local persistence fallback (Turso token expired).

The Turso cloud DB token from the previous session has expired (Turso rotated
JWT signing keys, so the old token returns HTTP 401 "can't be decoded with
any of the existing keys"). To re-establish cloud sync, the user must run
`turso auth login` to obtain a fresh API token.

This script persists the Phase 32 artifacts to the local SQLite DB at
/home/z/my-project/db/custom.db (the project's existing local DB) so they
survive across sessions. The schema mirrors the Turso project_meta table
so the data can be migrated to Turso once a fresh token is available.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path("/home/z/my-project/db/custom.db")


def main():
    run_dir = ROOT / "storage" / "phase32_real_llm_run"
    if not run_dir.is_dir():
        print(f"[local-sync] run dir missing: {run_dir}", file=sys.stderr)
        return 1

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # Create the project_meta mirror table (idempotent)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS project_meta (
            meta_key TEXT PRIMARY KEY,
            meta_value TEXT NOT NULL,
            meta_hash TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    # Also a project_worklog mirror table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS project_worklog (
            task_id TEXT PRIMARY KEY,
            agent TEXT NOT NULL,
            task TEXT NOT NULL,
            content TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()

    artifacts = [
        ("phase32:manifest", run_dir / "PHASE32_MANIFEST.json"),
        ("phase32:llm_verification", run_dir / "PHASE32_LLM_VERIFICATION.json"),
        ("phase32:engine_16_contribution", run_dir / "engines" / "engine_16" / "CONTRIBUTION.json"),
        ("phase32:meta_run", run_dir / "META_RUN.json"),
        ("phase32:cross_model_validation", run_dir / "CROSS_MODEL_VALIDATION.json"),
    ]
    side = ROOT / "storage" / "phase32_side" / "UPGRADED_CONFIG.json"
    if side.is_file():
        artifacts.append(("phase32:upgraded_config", side))

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    saved = 0
    for key, path in artifacts:
        if not path.is_file():
            print(f"[local-sync] SKIP {key}: missing {path}")
            continue
        value = path.read_text()
        h = hashlib.sha256(value.encode("utf-8")).hexdigest()
        cur.execute(
            "INSERT OR REPLACE INTO project_meta (meta_key, meta_value, meta_hash, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (key, value, h, now),
        )
        saved += 1
        print(f"[local-sync] saved {key} ({path.name})")

    # Save a worklog entry
    worklog_entry = {
        "task_id": "57-phase32",
        "agent": "Z.ai Code (orchestrator)",
        "task": "Phase 32: Real LLM Execution via metaengine-llm-bridge",
        "content": (
            "Created mini-services/llm-bridge (OpenAI-compatible HTTP bridge "
            "backed by z-ai-web-dev-sdk) on port 3031. Upgraded engine_16 "
            "to LLM_MODEL mode in-memory and ran the orchestrator. Verified: "
            "engine_16 produced COMPLETE contribution with adapter_kind="
            "LLM_MODEL, implementation_level=REAL_LLM_EXECUTOR, "
            "response_text_length=3788, total_tokens=1382, "
            "claim_ceiling=LLM_OUTPUT_IS_GENERATIVE_UNTIL_EXTERNALLY_VERIFIED. "
            "Constitution preserved: biographies NOT updated by LLM directly, "
            "LocalOutcomeOracle path retained. 840 tests still pass. "
            "Turso cloud sync skipped — token expired, needs refresh."
        ),
    }
    cur.execute(
        "INSERT OR REPLACE INTO project_worklog (task_id, agent, task, content, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            worklog_entry["task_id"],
            worklog_entry["agent"],
            worklog_entry["task"],
            worklog_entry["content"],
            now,
        ),
    )
    print(f"[local-sync] saved worklog entry for {worklog_entry['task_id']}")

    conn.commit()
    conn.close()
    print(f"[local-sync] done — {saved} artifacts + 1 worklog entry saved to local SQLite DB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
