"""Phase 34 — Sync recursive improvement results to Turso cloud DB."""

from __future__ import annotations

import json
import os
import sys
import time
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
        "requests": [{"type": "execute", "stmt": {"sql": sql, "args": args or []}}],
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
    run_dir = ROOT / "storage" / "phase34_recursive_improvement"
    if not run_dir.is_dir():
        print(f"[sync] run dir missing: {run_dir}", file=sys.stderr)
        return 1

    artifacts = [
        ("phase34:manifest", run_dir / "PHASE34_MANIFEST.json"),
        ("phase34:generation_comparison", run_dir / "GENERATION_COMPARISON.json"),
        ("phase34:g0_results", run_dir / "G0_RESULTS.json"),
        ("phase34:g1_results", run_dir / "G1_RESULTS.json"),
    ]

    saved = 0
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

    # Save worklog entry
    worklog = {
        "task_id": "60-phase34",
        "agent": "Z.ai Code (orchestrator)",
        "task": "Phase 34: Recursive self-improvement demonstration",
        "content": (
            "Ran G0 (random policy selection, 3 sealed tasks, real LLM via bridge) "
            "→ trained predictive model on 3 observations → ran G1 (predicted-best "
            "policy selection, same 3 tasks). Results: G0 accuracy=0.667 (2/3), "
            "G1 accuracy=0.667 (2/3), improvement_ratio=1.0000, g1_better=False. "
            "HONEST finding: with only 3 observations, the model could not improve "
            "selection beyond G0 baseline. This is the EXPECTED result for small "
            "sample sizes — the model needs more observations to learn useful "
            "policy-task correlations. The recursive improvement LOOP is "
            "operational (predict → run → record → predict), but the LEARNING "
            "signal requires more data. Constitution preserved: truth_effect=NONE, "
            "g1_policy_remains_shadow=true, no auto-promotion. 840 tests still pass."
        ),
    }
    try:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        sql = (
            "INSERT INTO metaengine_worklog "
            "(task_id, agent, task, content, created_at) "
            "VALUES (?, ?, ?, ?, ?)"
        )
        args = [
            {"type": "text", "value": worklog["task_id"]},
            {"type": "text", "value": worklog["agent"]},
            {"type": "text", "value": worklog["task"]},
            {"type": "text", "value": worklog["content"]},
            {"type": "text", "value": now},
        ]
        _execute(sql, args)
        print(f"[worklog] saved worklog entry for {worklog['task_id']}")
    except Exception as exc:
        print(f"[worklog] FAILED: {exc}", file=sys.stderr)
        _save_artifact("phase34:worklog_entry", worklog)

    print(f"\n[sync] done — {saved} artifacts saved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
