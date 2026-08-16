"""analyze_and_improve.py — Aggregate benchmark results and propose MetaEngine improvements.

Reads benchmark_task_result artifacts from:
  1. Local: storage/massive_benchmark_tasks_shard*/round_*/<task_id>/RESULT.json
  2. Cloud: Turso metaengine_artifacts WHERE artifact_kind='benchmark_task_result'

Produces:
  - storage/benchmark_analysis_<timestamp>.json  — full aggregated analysis
  - storage/benchmark_analysis_<timestamp>.md    — human-readable report
  - storage/improvement_patches_<timestamp>.json — concrete improvement patches
      (amplify rules, mechanism hypotheses, biography deltas)

Improvement patches are ADVISORY — they never modify code or run anything.
A human operator reviews them and decides which to apply.

Patch types:
  1. AMPLIFY_RULE — new heuristic rule for dspy_amplify.py
  2. MECHANISM_HYPOTHESIS — new mechanism candidate for mechanism_library.py
  3. BIOGRAPHY_DELTA — per-engine biography updates
  4. ROUTING_HINT — task-conditional routing hints

Usage:
  python3 scripts/analyze_and_improve.py [--use-turso] [--apply] [--verbose]
  --use-turso   Also read results from Turso cloud DB (default: local only)
  --apply       Write patches to metaengine/adaptation_patches/ directory
                (default: dry-run, only print summary)
  --verbose     Print per-task details as we aggregate
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict, Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path("/home/z/my-project/METAENGINE_SLICE3_RESTORED")
STORAGE = ROOT / "storage"
PATCHES_DIR = ROOT / "metaengine" / "adaptation_patches"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from sync_all_to_turso import _execute as turso_execute, _arg as turso_arg, now_iso as turso_now_iso
    TURSO_AVAILABLE = True
except Exception as exc:
    TURSO_AVAILABLE = False


# ---------------------------------------------------------------------------
# Result loading
# ---------------------------------------------------------------------------


@dataclass
class TaskResult:
    task_id: str
    category: str
    difficulty: str
    prompt: str
    ground_truth: str
    engine_answer: str
    engine_status: str
    runtime_sec: float
    deterministic_score: float
    deterministic_passed: bool
    zai_judge_correctness: float | None
    dialectical_depth: float
    dialectical_counts: dict
    constitution_score: float
    combined_score: float
    fitness: float
    error: str | None
    round_id: int | None = None
    shard: str | None = None
    judge_source: str | None = None

    @classmethod
    def from_result_json(cls, r: dict, *, round_id=None, shard=None) -> "TaskResult":
        det = r.get("deterministic_score", {}) or {}
        zai = r.get("zai_judge") or {}
        return cls(
            task_id=r.get("task_id", "?"),
            category=r.get("category", "?"),
            difficulty=r.get("difficulty", "?"),
            prompt=r.get("prompt", ""),
            ground_truth=r.get("ground_truth", ""),
            engine_answer=r.get("engine_answer", ""),
            engine_status=r.get("engine_status", "UNKNOWN"),
            runtime_sec=float(r.get("runtime_sec", 0.0)),
            deterministic_score=float(det.get("score", 0.0)),
            deterministic_passed=bool(det.get("passed", False)),
            zai_judge_correctness=float(zai.get("correctness")) if zai and "correctness" in zai else None,
            dialectical_depth=float(r.get("dialectical_depth", 0.0)),
            dialectical_counts=r.get("dialectical_counts", {}) or {},
            constitution_score=float(r.get("constitution_score", 0.0)),
            combined_score=float(r.get("combined_score", 0.0)),
            fitness=float(r.get("fitness", 0.0)),
            error=r.get("error"),
            round_id=round_id,
            shard=shard,
            judge_source=r.get("zai_judge", {}).get("judge_source") if isinstance(r.get("zai_judge"), dict) else None,
        )


def load_local_results() -> list[TaskResult]:
    results_by_task: dict[str, TaskResult] = {}
    shard_dirs = sorted(STORAGE.glob("massive_benchmark_tasks_shard*"))
    if not shard_dirs:
        legacy = STORAGE / "massive_benchmark_tasks"
        if legacy.is_dir():
            shard_dirs = [legacy]
    for shard_dir in shard_dirs:
        shard_name = shard_dir.name.replace("massive_benchmark_tasks", "").lstrip("_") or "default"
        for round_dir in sorted(shard_dir.glob("round_*")):
            try:
                round_id = int(round_dir.name.split("_")[1])
            except Exception:
                round_id = None
            for task_dir in sorted(round_dir.iterdir()):
                rf = task_dir / "RESULT.json"
                if not rf.is_file():
                    continue
                try:
                    r = json.loads(rf.read_text(encoding="utf-8"))
                    tr = TaskResult.from_result_json(r, round_id=round_id, shard=shard_name)
                    prev = results_by_task.get(tr.task_id)
                    if prev is None or (tr.round_id or 0) >= (prev.round_id or 0):
                        results_by_task[tr.task_id] = tr
                except Exception:
                    pass
    return list(results_by_task.values())


def load_turso_results() -> list[TaskResult]:
    if not TURSO_AVAILABLE:
        return []
    results_by_task: dict[str, TaskResult] = {}
    try:
        r = turso_execute(
            "SELECT payload_json, created_at FROM metaengine_artifacts "
            "WHERE artifact_kind = 'benchmark_task_result' ORDER BY created_at DESC"
        )
        if r.get("type") != "ok":
            return []
        rows = r["response"]["result"]["rows"]
        for row in rows:
            try:
                payload = json.loads(row[0]["value"])
                content = payload.get("content", "{}")
                rj = json.loads(content)
                tr = TaskResult.from_result_json(rj, round_id=rj.get("round_id"), shard="turso")
                if tr.task_id not in results_by_task:
                    results_by_task[tr.task_id] = tr
            except Exception:
                pass
    except Exception:
        pass
    return list(results_by_task.values())


def merge_results(local, turso) -> list[TaskResult]:
    by_task: dict[str, TaskResult] = {}
    for tr in turso + local:
        prev = by_task.get(tr.task_id)
        if prev is None or (tr.round_id or 0) >= (prev.round_id or 0):
            by_task[tr.task_id] = tr
    return list(by_task.values())


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


@dataclass
class CategoryStats:
    category: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    crashes: int = 0
    avg_fitness: float = 0.0
    avg_det_score: float = 0.0
    avg_combined: float = 0.0
    avg_depth: float = 0.0
    avg_constitution: float = 0.0
    avg_runtime: float = 0.0
    total_rival_forks: int = 0
    total_sublations: int = 0
    total_evidence_discriminators: int = 0
    total_dialectical_nodes: int = 0
    pass_rate: float = 0.0
    common_failures: list = field(default_factory=list)
    common_patterns: list = field(default_factory=list)


def aggregate(results: list[TaskResult]) -> dict[str, CategoryStats]:
    cats: dict[str, CategoryStats] = defaultdict(lambda: CategoryStats(category=""))
    for r in results:
        c = cats[r.category]
        c.category = r.category
        c.total += 1
        if r.engine_status in ("CRASH", "ERROR"):
            c.crashes += 1
        elif r.deterministic_passed:
            c.passed += 1
        else:
            c.failed += 1
        c.avg_fitness += r.fitness
        c.avg_det_score += r.deterministic_score
        c.avg_combined += r.combined_score
        c.avg_depth += r.dialectical_depth
        c.avg_constitution += r.constitution_score
        c.avg_runtime += r.runtime_sec
        c.total_rival_forks += r.dialectical_counts.get("RIVAL_FORK", 0)
        c.total_sublations += r.dialectical_counts.get("SUBLATION_WITH_RESIDUE", 0)
        c.total_evidence_discriminators += r.dialectical_counts.get("EVIDENCE_DISCRIMINATOR", 0)
        c.total_dialectical_nodes += r.dialectical_counts.get("total", 0)
    for c in cats.values():
        if c.total:
            n = c.total
            c.avg_fitness = round(c.avg_fitness / n, 4)
            c.avg_det_score = round(c.avg_det_score / n, 4)
            c.avg_combined = round(c.avg_combined / n, 4)
            c.avg_depth = round(c.avg_depth / n, 4)
            c.avg_constitution = round(c.avg_constitution / n, 4)
            c.avg_runtime = round(c.avg_runtime / n, 3)
            c.pass_rate = round(c.passed / n, 4)
    return cats


# ---------------------------------------------------------------------------
# Patch generation
# ---------------------------------------------------------------------------


@dataclass
class ImprovementPatch:
    patch_id: str
    patch_type: str  # AMPLIFY_RULE | MECHANISM_HYPOTHESIS | BIOGRAPHY_DELTA | ROUTING_HINT
    target_module: str
    title: str
    rationale: str
    patch_content: dict
    confidence: float
    generated_at: str

    def to_dict(self) -> dict:
        return asdict(self)


def _patch_id(content: dict) -> str:
    return hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()[:32]


def generate_patches(results, stats) -> list[ImprovementPatch]:
    patches: list[ImprovementPatch] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    failing_cats = [(c.category, c) for c in stats.values() if c.pass_rate < 0.5 and c.total >= 2]
    for cat, c in failing_cats:
        if cat == "SAFETY":
            content = {
                "rule_name": "BOOST_ABSTENTION_ON_ABSOLUTE_CERTAINTY_PROMPTS",
                "trigger_keywords": ["absolute certainty", "state with absolute", "treat as verified",
                                     "bypass constitution", "without checking"],
                "action": "increase_abstention_score",
                "delta": 0.2,
                "applies_to_categories": ["SAFETY"],
            }
            rationale = f"SAFETY tasks have pass_rate={c.pass_rate:.2%} ({c.passed}/{c.total}). Boosting abstention when prompts request absolute certainty should improve this."
            patches.append(ImprovementPatch(
                patch_id=_patch_id(content), patch_type="AMPLIFY_RULE",
                target_module="metaengine/dspy_amplify.py",
                title="Boost abstention on absolute-certainty prompts",
                rationale=rationale, patch_content=content,
                confidence=0.8, generated_at=now,
            ))
        elif cat == "ARITHMETIC":
            content = {
                "rule_name": "ROUTE_NUMERIC_TASKS_TO_DEDICATED_SOLVER",
                "trigger_keywords": ["multiplied by", "factorial", "square root", "GCD", "LCM", "remainder"],
                "action": "route_to_engine_05_or_external_calculator",
                "applies_to_categories": ["ARITHMETIC"],
                "expected_improvement": "ARITHMETIC pass_rate from {:.2%} to 0.7".format(c.pass_rate),
            }
            rationale = f"ARITHMETIC tasks have pass_rate={c.pass_rate:.2%} ({c.passed}/{c.total}). MetaEngine is dialectical, not arithmetic — routing numeric tasks to a dedicated solver should improve pass_rate."
            patches.append(ImprovementPatch(
                patch_id=_patch_id(content), patch_type="ROUTING_HINT",
                target_module="metaengine/learned_router.py",
                title="Route numeric tasks to dedicated solver",
                rationale=rationale, patch_content=content,
                confidence=0.7, generated_at=now,
            ))
        else:
            content = {
                "rule_name": f"INCREASE_DEEP_ENGINES_FOR_{cat}",
                "action": "max_deep_engines += 1",
                "applies_to_categories": [cat],
                "expected_improvement": f"{cat} pass_rate from {c.pass_rate:.2%} to 0.6",
            }
            rationale = f"{cat} pass_rate={c.pass_rate:.2%}. Increasing deep engine count may surface more relevant perspectives."
            patches.append(ImprovementPatch(
                patch_id=_patch_id(content), patch_type="AMPLIFY_RULE",
                target_module="metaengine/dspy_amplify.py",
                title=f"Increase deep engines for {cat} tasks",
                rationale=rationale, patch_content=content,
                confidence=0.5, generated_at=now,
            ))

    # Successful categories → MECHANISM_HYPOTHESIS
    successful_cats = [(c.category, c) for c in stats.values() if c.pass_rate >= 0.5 and c.total >= 2]
    for cat, c in successful_cats:
        if c.avg_depth >= 0.8:
            content = {
                "mechanism_id": f"mech_{cat.lower()}_deep_dialectical_v1",
                "name": f"{cat.title()} Deep Dialectical Pattern",
                "description": f"{cat} tasks benefit from {c.avg_depth:.2f} dialectical depth",
                "evidence": {
                    "pass_rate": c.pass_rate,
                    "avg_fitness": c.avg_fitness,
                    "avg_depth": c.avg_depth,
                    "rival_forks_per_task": c.total_rival_forks / max(1, c.total),
                    "sublations_per_task": c.total_sublations / max(1, c.total),
                },
                "applicable_to_categories": [cat],
            }
            rationale = f"{cat} tasks pass at {c.pass_rate:.2%} with depth={c.avg_depth:.2f}. Capturing this pattern as a reusable mechanism."
            patches.append(ImprovementPatch(
                patch_id=_patch_id(content), patch_type="MECHANISM_HYPOTHESIS",
                target_module="metaengine/mechanism_library.py",
                title=f"Capture {cat} dialectical pattern as mechanism",
                rationale=rationale, patch_content=content,
                confidence=0.6, generated_at=now,
            ))

    # Crash detection → BIOGRAPHY_DELTA on failing engines
    crashes_by_shard = Counter(r.shard for r in results if r.engine_status in ("CRASH", "ERROR"))
    if crashes_by_shard:
        for shard, count in crashes_by_shard.most_common(3):
            content = {
                "engine_id": f"shard_{shard}",
                "delta": {"reliability_score": -0.1},
                "reason": f"{count} crashes observed",
            }
            rationale = f"Shard '{shard}' had {count} crashes — suggesting reliability issues."
            patches.append(ImprovementPatch(
                patch_id=_patch_id(content), patch_type="BIOGRAPHY_DELTA",
                target_module="metaengine/biographies.py",
                title=f"Decrease reliability for shard {shard} due to crashes",
                rationale=rationale, patch_content=content,
                confidence=0.9, generated_at=now,
            ))

    return patches


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def write_report(results, stats, patches, out_json, out_md) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    analysis = {
        "generated_at": timestamp,
        "total_results": len(results),
        "categories": {cat: c.to_dict() if hasattr(c, 'to_dict') else asdict(c) for cat, c in stats.items()},
        "patches_generated": len(patches),
        "patches": [p.to_dict() for p in patches],
    }
    out_json.write_text(json.dumps(analysis, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    lines = [
        f"# MetaEngine Benchmark Analysis — {timestamp}",
        "",
        f"**Total results aggregated**: {len(results)}",
        "",
        "## Per-category summary",
        "",
        "| Category | Total | Pass | Fail | Crash | Pass% | Avg Fit | Det | Depth | Rivals | Subl | RT(s) |",
        "|----------|------:|----:|----:|------:|------:|--------:|----:|------:|-------:|-----:|------:|",
    ]
    for cat in sorted(stats.keys()):
        c = stats[cat]
        lines.append(
            f"| {cat} | {c.total} | {c.passed} | {c.failed} | {c.crashes} | "
            f"{c.pass_rate:.1%} | {c.avg_fitness:.3f} | {c.avg_det_score:.3f} | "
            f"{c.avg_depth:.3f} | {c.total_rival_forks} | {c.total_sublations} | {c.avg_runtime:.1f} |"
        )
    lines.append("")
    lines.append(f"## Improvement patches generated: {len(patches)}")
    lines.append("")
    for i, p in enumerate(patches, 1):
        lines.append(f"### {i}. [{p.patch_type}] {p.title}")
        lines.append(f"**Target**: `{p.target_module}`  ")
        lines.append(f"**Confidence**: {p.confidence:.0%}  ")
        lines.append(f"**Rationale**: {p.rationale}  ")
        lines.append(f"**Patch content**:")
        lines.append("```json")
        lines.append(json.dumps(p.patch_content, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--use-turso", action="store_true", help="Also read from Turso")
    ap.add_argument("--apply", action="store_true", help="Write patches to disk")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    print("=== Loading local results ===")
    local = load_local_results()
    print(f"  Local results: {len(local)}")
    turso = []
    if args.use_turso:
        print("=== Loading Turso results ===")
        turso = load_turso_results()
        print(f"  Turso results: {len(turso)}")
    results = merge_results(local, turso)
    print(f"  Merged (latest wins): {len(results)}")

    if args.verbose and results:
        print("\n=== Per-task summary (verbose) ===")
        for r in results[:20]:
            print(f"  {r.task_id:12s} {r.category:10s} fit={r.fitness:.3f} det={r.deterministic_score:.2f} "
                  f"depth={r.dialectical_depth:.2f} rivals={r.dialectical_counts.get('RIVAL_FORK',0)} "
                  f"judge={r.judge_source or 'none'}")

    print("\n=== Aggregating by category ===")
    stats = aggregate(results)
    for cat in sorted(stats.keys()):
        c = stats[cat]
        print(f"  {cat:12s} n={c.total:3d} pass={c.pass_rate:.1%} fit={c.avg_fitness:.3f} "
              f"depth={c.avg_depth:.3f} rivals={c.total_rival_forks} sublations={c.total_sublations}")

    print("\n=== Generating improvement patches ===")
    patches = generate_patches(results, stats)
    for p in patches:
        print(f"  [{p.patch_type}] {p.title} (confidence={p.confidence:.0%})")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_json = STORAGE / f"benchmark_analysis_{timestamp}.json"
    out_md = STORAGE / f"benchmark_analysis_{timestamp}.md"
    write_report(results, stats, patches, out_json, out_md)
    print(f"\n✓ JSON report: {out_json}")
    print(f"✓ Markdown report: {out_md}")

    if args.apply and patches:
        PATCHES_DIR.mkdir(parents=True, exist_ok=True)
        for p in patches:
            pf = PATCHES_DIR / f"{p.patch_type.lower()}_{p.patch_id}.json"
            pf.write_text(json.dumps(p.to_dict(), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            print(f"  ✓ Written: {pf.name}")
        print(f"\n✓ {len(patches)} patches written to {PATCHES_DIR}")
        print("  These are ADVISORY — a human operator must review and decide which to apply.")
    elif patches:
        print(f"\n{len(patches)} patches generated (dry-run). Use --apply to write them to disk.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
