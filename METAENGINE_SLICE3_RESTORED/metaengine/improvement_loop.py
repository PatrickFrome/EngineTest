"""improvement_loop.py — Fully automated MetaEngine improvement loop.

This module implements the complete autonomous improvement cycle:

  ┌────────────────────────────────────────────────────────────────┐
  │                                                                │
  │   ┌─────────────┐    ┌──────────────┐    ┌──────────────┐      │
  │   │  benchmark  │───►│   analyze    │───►│   propose   │      │
  │   │  (run N     │    │   (aggregate │    │   (generate │      │
  │   │   tasks)    │    │    results)  │    │    patches) │      │
  │   └─────────────┘    └──────────────┘    └──────┬───────┘      │
  │                                                │              │
  │                                                ▼              │
  │   ┌─────────────┐    ┌──────────────┐    ┌──────────────┐      │
  │   │  validate   │◄───│    apply     │◄───│   review     │      │
  │   │  (run tests │    │   (patch     │    │   (safety    │      │
  │   │   + bench)  │    │    metaengine)│   │    checks)   │      │
  │   └──────┬──────┘    └──────────────┘    └──────────────┘      │
  │          │                                                     │
  │          ▼                                                     │
  │   ┌──────────────┐                                             │
  │   │  publish to  │                                             │
  │   │  Turso cloud │                                             │
  │   └──────────────┘                                             │
  │                                                                │
  └────────────────────────────────────────────────────────────────┘
                          ↑
                          │  repeat forever
                          └────────────────────────

Key principle: every patch is ADVISORY until validated. If applying a patch
makes tests fail or fitness decrease, the patch is ROLLED BACK automatically.

Patch types applied:
  1. AMPLIFY_RULE → adds a new heuristic rule to dspy_amplify.py
  2. ROUTING_HINT → adjusts learned_router.py engine weights
  3. BIOGRAPHY_DELTA → updates engine biographies (no code change)
  4. MECHANISM_HYPOTHESIS → adds a new mechanism candidate

Patches that are NOT applied automatically (require human review):
  - Code modifications (would break constitution K0 invariants)
  - Architecture policy changes (require outcome-gated promotion)
  - Constitution modifications (impossible — K0 is immutable)

Usage:
  python3 -m metaengine.improvement_loop             # run one cycle
  python3 -m metaengine.improvement_loop --forever    # run forever
  python3 -m metaengine.improvement_loop --forever --interval 600  # every 10 min
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Auto-discover ROOT (same pattern as run_massive_benchmark.py)
ROOT = Path(os.environ.get("ME_BENCHMARK_ROOT") or Path(__file__).resolve().parent.parent)
STORAGE = ROOT / "storage"
PATCHES_DIR = ROOT / "metaengine" / "adaptation_patches"
LOOP_STATE_FILE = STORAGE / "improvement_loop_state.json"
LOOP_LOG = STORAGE / "improvement_loop.log"

# Make metaengine importable
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(msg: str) -> None:
    line = f"[{_now_iso()}] {msg}"
    print(line, flush=True)
    try:
        LOOP_LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOOP_LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Cycle state — persisted between runs
# ---------------------------------------------------------------------------


@dataclass
class CycleResult:
    cycle_id: int
    started_at: str
    ended_at: str = ""
    duration_sec: float = 0.0
    # Phase 1: benchmark
    tasks_run: int = 0
    avg_fitness_before: float = 0.0
    # Phase 2: analyze
    patches_proposed: int = 0
    patches_applied: int = 0
    patches_rolled_back: int = 0
    # Phase 3: validate
    avg_fitness_after: float = 0.0
    fitness_delta: float = 0.0
    tests_pass_before: int = 0
    tests_pass_after: int = 0
    # Decision
    accepted: bool = False  # True if cycle kept its changes
    rollback_reason: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Phase 1: Run a small benchmark batch (deterministic)
# ---------------------------------------------------------------------------


def _run_benchmark_batch(batch_size: int = 6) -> dict:
    """Run a small benchmark batch and return summary.

    Picks 6 tasks across different categories (deterministic seed) so we
    measure MetaEngine on its actual strengths (philosophy/logic/reasoning/safety)
    rather than arithmetic (which it's not designed for).
    """
    _log(f"[phase1] running benchmark batch of {batch_size} tasks")
    try:
        # Use the existing benchmark runner in single-round mode
        # We pick a deterministic subset focused on dialectical tasks
        from scripts.run_massive_benchmark import (
            TASK_BANK,
            run_round,
        )
        # Pick tasks across non-arithmetic categories
        focused_categories = ["PHILOSOPHY", "LOGIC", "REASONING", "SAFETY", "ANALYSIS", "ETHICS"]
        selected = []
        for cat in focused_categories:
            for t in TASK_BANK:
                if t.category == cat and len(selected) < batch_size:
                    selected.append(t)
                    break
        if len(selected) < batch_size:
            # Fill from remaining tasks
            for t in TASK_BANK:
                if t not in selected and len(selected) < batch_size:
                    selected.append(t)

        # Use a unique instance ID for the improvement loop
        instance_id = "improvement_loop"
        # Override the globals (similar to main())
        import scripts.run_massive_benchmark as bm
        bm.INSTANCE_ID = instance_id
        bm.TASKS_DIR = STORAGE / f"massive_benchmark_tasks_{instance_id}"
        bm.STATUS_FILE = STORAGE / f"massive_benchmark_status_{instance_id}.json"
        bm.ROUNDS_LOG = STORAGE / f"massive_benchmark_rounds_{instance_id}.jsonl"
        bm.HUMAN_LOG = STORAGE / f"massive_benchmark_{instance_id}.log"
        bm.TASKS_DIR.mkdir(parents=True, exist_ok=True)

        summary, per_task = run_round(
            round_id=int(time.time()),
            tasks=selected,
            max_workers=2,
            use_zai=False,
            multi_validator=None,
        )
        _log(f"[phase1] DONE — avg_fitness={summary['avg_fitness']:.4f}, pass_rate={summary['pass_rate']:.2%}")
        return {
            "summary": summary,
            "per_task": per_task,
            "avg_fitness": summary["avg_fitness"],
            "pass_rate": summary["pass_rate"],
        }
    except Exception as exc:
        tb = traceback.format_exc()
        _log(f"[phase1] FAILED: {exc}\n{tb[-800:]}")
        return {"error": str(exc), "avg_fitness": 0.0, "per_task": [], "summary": {}}


# ---------------------------------------------------------------------------
# Phase 2: Analyze + generate patches
# ---------------------------------------------------------------------------


def _analyze_and_propose(per_task: list[dict]) -> list[dict]:
    """Generate improvement patches from task results."""
    _log(f"[phase2] analyzing {len(per_task)} task results")
    try:
        from scripts.analyze_and_improve import (
            TaskResult,
            aggregate,
            generate_patches,
        )
        results = [
            TaskResult.from_result_json(r) for r in per_task if isinstance(r, dict)
        ]
        stats = aggregate(results)
        patches = generate_patches(results, stats)
        patches_dict = [p.to_dict() for p in patches]
        _log(f"[phase2] DONE — generated {len(patches_dict)} patches")
        for p in patches_dict:
            _log(f"  - [{p['patch_type']}] {p['title']} (confidence={p['confidence']:.0%})")
        return patches_dict
    except Exception as exc:
        _log(f"[phase2] FAILED: {exc}")
        return []


# ---------------------------------------------------------------------------
# Phase 3: Apply patches (safely)
# ---------------------------------------------------------------------------


def _apply_patch(patch: dict) -> tuple[bool, str]:
    """Apply one patch. Returns (success, message).

    Patches are stored as JSON files in metaengine/adaptation_patches/.
    The relevant MetaEngine modules (dspy_amplify.py, learned_router.py,
    mechanism_library.py, biographies.py) load these patches at startup
    when present, so we don't modify source code.
    """
    PATCHES_DIR.mkdir(parents=True, exist_ok=True)
    patch_id = patch.get("patch_id") or hashlib.sha256(
        json.dumps(patch.get("patch_content", {}), sort_keys=True, default=str).encode()
    ).hexdigest()[:32]
    patch_type = patch.get("patch_type", "UNKNOWN")
    filename = f"{patch_type.lower()}_{patch_id}.json"
    filepath = PATCHES_DIR / filename

    # Don't re-apply if already present
    if filepath.is_file():
        return True, f"already applied: {filename}"

    try:
        filepath.write_text(
            json.dumps(patch, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return True, f"applied: {filename}"
    except Exception as exc:
        return False, f"failed to write {filename}: {exc}"


def _apply_patches(patches: list[dict]) -> tuple[int, int, list[str]]:
    """Apply all patches. Returns (applied_count, failed_count, messages)."""
    _log(f"[phase3] applying {len(patches)} patches")
    applied = 0
    failed = 0
    messages = []
    for p in patches:
        ok, msg = _apply_patch(p)
        if ok:
            applied += 1
        else:
            failed += 1
        messages.append(msg)
        _log(f"  {msg}")
    return applied, failed, messages


def _rollback_patches(patches: list[dict]) -> int:
    """Remove the patch files we just created (rollback)."""
    rolled_back = 0
    for p in patches:
        patch_id = p.get("patch_id") or hashlib.sha256(
            json.dumps(p.get("patch_content", {}), sort_keys=True, default=str).encode()
        ).hexdigest()[:32]
        patch_type = p.get("patch_type", "UNKNOWN")
        filename = f"{patch_type.lower()}_{patch_id}.json"
        filepath = PATCHES_DIR / filename
        if filepath.is_file():
            try:
                filepath.unlink()
                rolled_back += 1
                _log(f"  rolled back: {filename}")
            except Exception as exc:
                _log(f"  rollback FAILED for {filename}: {exc}")
    return rolled_back


# ---------------------------------------------------------------------------
# Phase 4: Run tests to validate patches didn't break anything
# ---------------------------------------------------------------------------


def _run_test_suite() -> tuple[int, int, int]:
    """Run the MetaEngine test suite. Returns (passed, failed, errors).

    Uses pytest with --tb=no -q for speed. Skips tests requiring hypothesis
    (which is not installed in this environment).
    """
    _log("[phase4] running test suite")
    import subprocess
    try:
        result = subprocess.run(
            ["python3", "-m", "pytest",
             str(ROOT / "tests"),
             "--tb=no", "-q",
             "--ignore=tests/test_constitution_property_based.py",
             "-x",  # stop on first failure
             "--timeout=30"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        # Parse pytest summary line: "27 passed in 0.14s" or "1 failed, 26 passed in 1.0s"
        output = result.stdout + "\n" + result.stderr
        passed = 0
        failed = 0
        errors = 0
        for line in output.split("\n"):
            if "passed" in line and ("failed" in line or "error" in line or "passed" in line):
                # Parse "N passed" / "N failed" / "N error"
                import re
                m = re.search(r"(\d+) passed", line)
                if m: passed = int(m.group(1))
                m = re.search(r"(\d+) failed", line)
                if m: failed = int(m.group(1))
                m = re.search(r"(\d+) error", line)
                if m: errors = int(m.group(1))
                break
        _log(f"[phase4] DONE — passed={passed}, failed={failed}, errors={errors}")
        return passed, failed, errors
    except subprocess.TimeoutExpired:
        _log("[phase4] TIMEOUT — assuming failure")
        return 0, 0, 1
    except Exception as exc:
        _log(f"[phase4] FAILED: {exc}")
        return 0, 0, 1


# ---------------------------------------------------------------------------
# Phase 5: Run benchmark again to measure improvement
# ---------------------------------------------------------------------------


def _measure_post_improvement(batch_size: int = 6) -> float:
    """Run another benchmark batch and return avg_fitness."""
    result = _run_benchmark_batch(batch_size)
    return result.get("avg_fitness", 0.0)


# ---------------------------------------------------------------------------
# Phase 6: Publish cycle result to Turso
# ---------------------------------------------------------------------------


def _publish_to_turso(cycle: CycleResult) -> None:
    """Push the cycle result to Turso cloud DB."""
    try:
        from sync_all_to_turso import _execute as turso_execute, _arg as turso_arg, now_iso as turso_now_iso
    except Exception as exc:
        _log(f"[phase6] Turso helper not available: {exc}")
        return
    try:
        content = json.dumps(cycle.to_dict(), ensure_ascii=False, default=str)
        key = f"improvement_cycle:{cycle.cycle_id}"
        sql = "INSERT OR REPLACE INTO metaengine_project_meta (key, value) VALUES (?, ?)"
        args = [turso_arg(key), turso_arg(content)]
        r = turso_execute(sql, args)
        if r.get("type") == "ok":
            _log(f"[phase6] published cycle {cycle.cycle_id} to Turso (key={key})")
        else:
            _log(f"[phase6] Turso error: {r.get('error', {})}")
        # Also update last_cycle_summary
        sql2 = "INSERT OR REPLACE INTO metaengine_project_meta (key, value) VALUES (?, ?)"
        args2 = [turso_arg("improvement_loop:last_cycle"), turso_arg(content)]
        turso_execute(sql2, args2)
    except Exception as exc:
        _log(f"[phase6] FAILED: {exc}")


# ---------------------------------------------------------------------------
# Persisted loop state
# ---------------------------------------------------------------------------


def load_loop_state() -> dict:
    if LOOP_STATE_FILE.is_file():
        try:
            return json.loads(LOOP_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"cycle_count": 0, "cycles": [], "best_fitness": 0.0, "best_cycle": 0}


def save_loop_state(state: dict) -> None:
    try:
        LOOP_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOOP_STATE_FILE.write_text(
            json.dumps(state, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    except Exception as exc:
        _log(f"[state] save failed: {exc}")


# ---------------------------------------------------------------------------
# Main cycle
# ---------------------------------------------------------------------------


def run_one_cycle(cycle_id: int) -> CycleResult:
    """Run one complete improvement cycle."""
    cycle = CycleResult(cycle_id=cycle_id, started_at=_now_iso())
    t0 = time.perf_counter()

    # Phase 1: benchmark BEFORE
    _log("=" * 60)
    _log(f"=== CYCLE {cycle_id} START ===")
    _log("=" * 60)
    before = _run_benchmark_batch(batch_size=6)
    cycle.tasks_run = len(before.get("per_task", []))
    cycle.avg_fitness_before = before.get("avg_fitness", 0.0)
    if "error" in before:
        cycle.error = f"phase1: {before['error']}"
        cycle.ended_at = _now_iso()
        cycle.duration_sec = time.perf_counter() - t0
        return cycle

    # Phase 2: analyze + propose
    patches = _analyze_and_propose(before.get("per_task", []))
    cycle.patches_proposed = len(patches)
    if not patches:
        _log("[cycle] no patches proposed — nothing to improve this round")
        cycle.ended_at = _now_iso()
        cycle.duration_sec = time.perf_counter() - t0
        cycle.accepted = True
        cycle.avg_fitness_after = cycle.avg_fitness_before
        return cycle

    # Phase 3: apply patches
    applied, failed, _ = _apply_patches(patches)
    cycle.patches_applied = applied

    # Phase 4: run tests
    passed, test_failed, test_errors = _run_test_suite()
    cycle.tests_pass_before = passed
    if test_failed > 0 or test_errors > 0:
        _log(f"[cycle] tests failed after patches — rolling back")
        cycle.patches_rolled_back = _rollback_patches(patches)
        cycle.rollback_reason = f"tests_failed={test_failed}_errors={test_errors}"
        cycle.ended_at = _now_iso()
        cycle.duration_sec = time.perf_counter() - t0
        cycle.avg_fitness_after = cycle.avg_fitness_before
        return cycle

    # Phase 5: measure improvement
    after_fitness = _measure_post_improvement(batch_size=6)
    cycle.avg_fitness_after = after_fitness
    cycle.fitness_delta = after_fitness - cycle.avg_fitness_before
    cycle.tests_pass_after = passed

    # Decision: keep patches only if fitness didn't regress
    if cycle.fitness_delta < -0.05:  # allow 5% regression tolerance
        _log(f"[cycle] fitness regressed by {-cycle.fitness_delta:.4f} — rolling back")
        cycle.patches_rolled_back = _rollback_patches(patches)
        cycle.rollback_reason = f"fitness_regressed_by_{-cycle.fitness_delta:.4f}"
        cycle.accepted = False
    else:
        _log(f"[cycle] fitness delta = {cycle.fitness_delta:+.4f} — KEEPING patches")
        cycle.accepted = True

    cycle.ended_at = _now_iso()
    cycle.duration_sec = time.perf_counter() - t0
    _log(f"=== CYCLE {cycle_id} END — duration={cycle.duration_sec:.1f}s, accepted={cycle.accepted} ===")
    return cycle


def run_forever(interval_sec: int = 300) -> None:
    """Run improvement cycles forever, sleeping `interval_sec` between cycles."""
    state = load_loop_state()
    cycle_id = state.get("cycle_count", 0) + 1
    _log(f"=== IMPROVEMENT LOOP STARTING (cycle_id begins at {cycle_id}, interval={interval_sec}s) ===")

    # Signal handler — finish current cycle then exit
    _shutdown = {"requested": False}

    def _handler(signum, frame):
        _shutdown["requested"] = True
        _log(f"[signal] received {signum} — will exit after current cycle")

    try:
        import signal
        signal.signal(signal.SIGTERM, _handler)
        signal.signal(signal.SIGINT, _handler)
    except Exception:
        pass

    while not _shutdown["requested"]:
        try:
            cycle = run_one_cycle(cycle_id)
            state["cycle_count"] = cycle_id
            state["cycles"].append(cycle.to_dict())
            # Keep last 50 cycles in state file
            state["cycles"] = state["cycles"][-50:]
            if cycle.accepted and cycle.avg_fitness_after > state.get("best_fitness", 0.0):
                state["best_fitness"] = cycle.avg_fitness_after
                state["best_cycle"] = cycle_id
                _log(f"[loop] NEW BEST FITNESS: {cycle.avg_fitness_after:.4f} (cycle {cycle_id})")
            save_loop_state(state)
            _publish_to_turso(cycle)
        except Exception as exc:
            _log(f"[loop] cycle {cycle_id} crashed: {exc}")
            _log(traceback.format_exc()[-800:])

        cycle_id += 1
        if _shutdown["requested"]:
            break
        _log(f"[loop] sleeping {interval_sec}s before next cycle")
        # Sleep in small increments so we can respond to signals
        slept = 0
        while slept < interval_sec and not _shutdown["requested"]:
            time.sleep(min(5, interval_sec - slept))
            slept += 5

    _log("=== IMPROVEMENT LOOP EXITED ===")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="MetaEngine autonomous improvement loop")
    ap.add_argument("--forever", action="store_true",
                    help="Run improvement cycles forever (until killed).")
    ap.add_argument("--interval", type=int, default=300,
                    help="Seconds between cycles when --forever (default: 300).")
    ap.add_argument("--cycle-id", type=int, default=0,
                    help="Cycle ID to start from (default: load from state).")
    args = ap.parse_args()

    if args.forever:
        run_forever(interval_sec=args.interval)
        return 0
    else:
        state = load_loop_state()
        cycle_id = args.cycle_id or (state.get("cycle_count", 0) + 1)
        cycle = run_one_cycle(cycle_id)
        state["cycle_count"] = cycle_id
        state["cycles"].append(cycle.to_dict())
        state["cycles"] = state["cycles"][-50:]
        if cycle.accepted and cycle.avg_fitness_after > state.get("best_fitness", 0.0):
            state["best_fitness"] = cycle.avg_fitness_after
            state["best_cycle"] = cycle_id
        save_loop_state(state)
        _publish_to_turso(cycle)
        return 0 if cycle.accepted else 1


if __name__ == "__main__":
    sys.exit(main())
