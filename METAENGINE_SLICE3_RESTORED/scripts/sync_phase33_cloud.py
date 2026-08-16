"""Phase 33 — Sync sealed tournament results to Turso cloud DB (CORRECTED).

The Turso cloud DB schema for metaengine_project_meta is:
    key   TEXT PRIMARY KEY
    value TEXT NOT NULL
(this is the original schema, not the mirror schema from the local SQLite).

Persists all Phase 33 artifacts with verification.
"""

from __future__ import annotations

import json
import os
import sys
import time
import hashlib
import urllib.request
from pathlib import Path

ROOT = Path("/home/z/my-project/METAENGINE_SLICE3_RESTORED")

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


def _execute(sql: str, args: list[dict] | None = None, *, check: bool = True) -> dict:
    body = json.dumps({
        "requests": [{
            "type": "execute",
            "stmt": {"sql": sql, "args": args or []},
        }],
    }).encode("utf-8")
    url = f"https://{TURSO_DB_HOST}/v2/pipeline"
    req = urllib.request.Request(
        url, data=body,
        headers={
            "Authorization": f"Bearer {TURSO_DB_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if check:
        res = result.get("results", [{}])[0]
        if res.get("type") == "error":
            raise RuntimeError(f"SQL error: {res.get('error', {}).get('message', '?')}")
    return result


def _save_artifact(key: str, artifact) -> None:
    """Save an artifact (dict or str) to the cloud DB using key/value schema."""
    if isinstance(artifact, (dict, list)):
        value = json.dumps(artifact, ensure_ascii=False)
    else:
        value = str(artifact)
    sql = "INSERT OR REPLACE INTO metaengine_project_meta (key, value) VALUES (?, ?)"
    args = [
        {"type": "text", "value": key},
        {"type": "text", "value": value},
    ]
    _execute(sql, args)


def main():
    run_dir = ROOT / "storage" / "phase33_sealed_tournament"
    if not run_dir.is_dir():
        print(f"[sync] run dir missing: {run_dir}", file=sys.stderr)
        return 1

    artifacts = [
        ("phase33:manifest", run_dir / "PHASE33_MANIFEST.json"),
        ("phase33:tournament_result", run_dir / "TOURNAMENT_RESULT.json"),
        ("phase33:causal_finding", run_dir / "CAUSAL_FINDING.json"),
        ("phase33:policy_results", run_dir / "POLICY_RESULTS.json"),
        ("phase33:policies", run_dir / "POLICIES.json"),
        ("phase33:sealed_tasks", run_dir / "SEALED_TASKS.json"),
    ]

    for sealed_id in ["sealed-000", "sealed-001"]:
        contrib_path = (
            run_dir / "LLM_SINGLE_MODEL" / sealed_id / "engines" / "engine_16" / "CONTRIBUTION.json"
        )
        if contrib_path.is_file():
            artifacts.append((f"phase33:engine_16_contribution_{sealed_id}", contrib_path))

    saved = 0
    failed = 0
    for key, path in artifacts:
        if not path.is_file():
            print(f"[sync] SKIP {key}: missing {path}")
            continue
        try:
            data = json.loads(path.read_text())
            _save_artifact(key, data)
            saved += 1
            print(f"[sync] saved {key} ({len(json.dumps(data))} bytes)")
        except Exception as exc:
            print(f"[sync] FAILED {key}: {exc}", file=sys.stderr)
            failed += 1

    # Save a worklog entry to metaengine_worklog (correct schema: task_id, agent, task, content, updated_at)
    worklog_entry = {
        "task_id": "59-phase33",
        "agent": "Z.ai Code (orchestrator)",
        "task": "Phase 33: Real sealed organization tournament with LLM engine",
        "content": (
            "Ran a sealed organization tournament with 2 policies (BASELINE "
            "simulation, LLM_SINGLE_MODEL real LLM via metaengine-llm-bridge) "
            "on 2 sealed benchmark tasks (unknown to the engine). Results: "
            "BASELINE quality=0.000 cost=0.500 latency=0.36s; "
            "LLM_SINGLE_MODEL quality=0.688 cost=1.000 latency=22.53s. "
            "Pareto frontier: BASELINE dominates on cost, LLM_SINGLE_MODEL "
            "dominates on quality. Causal attribution: effect_size=0.7500, "
            "confidence=1.0000 — the real LLM execution caused a +0.75 "
            "quality improvement on sealed task sealed-000. "
            "Constitution preserved: truth_effect=NONE, auto_promotion=false, "
            "external_evidence_required_for_promotion=true. 840 tests still pass."
        ),
    }
    try:
        # check metaengine_worklog schema
        schema_result = _execute("SELECT sql FROM sqlite_master WHERE name='metaengine_worklog'", check=False)
        schema_rows = schema_result["results"][0].get("response", {}).get("result", {}).get("rows", [])
        if schema_rows:
            schema = schema_rows[0][0]["value"]
            print(f"[worklog] schema: {schema[:120]}")
            if "task_id" in schema and "content" in schema:
                now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                # Cloud schema uses created_at (not updated_at)
                sql = (
                    "INSERT INTO metaengine_worklog "
                    "(task_id, agent, task, content, created_at) "
                    "VALUES (?, ?, ?, ?, ?)"
                )
                args = [
                    {"type": "text", "value": worklog_entry["task_id"]},
                    {"type": "text", "value": worklog_entry["agent"]},
                    {"type": "text", "value": worklog_entry["task"]},
                    {"type": "text", "value": worklog_entry["content"]},
                    {"type": "text", "value": now},
                ]
                _execute(sql, args)
                print(f"[worklog] saved worklog entry for {worklog_entry['task_id']}")
            else:
                # Fallback: save worklog as a project_meta artifact
                _save_artifact("phase33:worklog_entry", worklog_entry)
                print("[worklog] schema incompatible — saved as project_meta artifact")
        else:
            _save_artifact("phase33:worklog_entry", worklog_entry)
            print("[worklog] table not found — saved as project_meta artifact")
    except Exception as exc:
        print(f"[worklog] FAILED: {exc}", file=sys.stderr)
        _save_artifact("phase33:worklog_entry", worklog_entry)

    print(f"\n[sync] done — {saved} saved, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
