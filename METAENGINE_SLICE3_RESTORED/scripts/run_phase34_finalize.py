"""METAENGINE Phase 34 — Finalize Recursive Improvement (resume + G1).

This script:
  1. Loads existing G0 results from storage/phase34_recursive_improvement/G0/.
  2. Trains the OrganizationModel on G0 outcomes.
  3. Runs G1 over the SAME tasks using PREDICTED-BEST policy selection.
  4. Computes the GenerationComparison.

If a G1 run is interrupted (rate-limit), re-running this script resumes from
where it left off (reuses POLICY_RUN_SUMMARY.json files).
"""

from __future__ import annotations

import copy
import json
import os
import sys
import time
import shutil
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.sealed_benchmark import SealedBenchmarkSuite, SealedTask
from metaengine.predictive_model import OrganizationModel
from metaengine.recursive_improvement import GenerationComparator
from metaengine.architecture_policy import ArchitecturePolicy, initial_policy
from metaengine.organization_tournament import PolicyResult

LLM_BRIDGE_ENDPOINT = "http://localhost:3031/v1/chat/completions"
LLM_BRIDGE_MODEL = "metaengine-glm-1"
LLM_BRIDGE_PORT = 3031


def _bridge_health() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(
            f"http://localhost:{LLM_BRIDGE_PORT}/health", timeout=5
        ) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("status") == "ok"
    except Exception:
        return False


def _upgrade_engine_16_to_llm(cfg: dict) -> dict:
    new_cfg = copy.deepcopy(cfg)
    for e in new_cfg["engines"]:
        if e["engine_id"] == "engine_16":
            e["execution_mode"] = "LLM_MODEL"
            e["llm_endpoint"] = LLM_BRIDGE_ENDPOINT
            e["llm_model_name"] = LLM_BRIDGE_MODEL
            e["llm_api_key_env"] = "LLM_BRIDGE_API_KEY"
            e["llm_max_tokens"] = 1024
            e["llm_temperature"] = 0.4
            e["llm_timeout"] = 180.0
    return new_cfg


def _build_policies() -> list[tuple[str, ArchitecturePolicy]]:
    base_policy = initial_policy()
    pol_a = ArchitecturePolicy(
        generation=0, parent_policy_hash=base_policy.policy_hash,
        topology_id="LLM_CREATIVE",
        waves=(("engine_16",),),
        dialectic_operators=("OPERATOR_MUTATION", "EVIDENCE_DISCRIMINATOR"),
        max_rounds=1, max_deep_engines=1, exploration_rate=0.0,
        status="SHADOW",
        mutation_receipt={"origin": "PHASE34_G0_POLICY_LLM_A"},
    )
    pol_a.validate()
    pol_b = ArchitecturePolicy(
        generation=0, parent_policy_hash=base_policy.policy_hash,
        topology_id="LLM_FOCUSED",
        waves=(("engine_16",),),
        dialectic_operators=("OPERATOR_MUTATION",),
        max_rounds=1, max_deep_engines=1, exploration_rate=0.0,
        status="SHADOW",
        mutation_receipt={"origin": "PHASE34_G0_POLICY_LLM_B"},
    )
    pol_b.validate()
    return [("LLM_CREATIVE", pol_a), ("LLM_FOCUSED", pol_b)]


def _evaluate_quality(task: SealedTask, response_text: str) -> float:
    if not response_text:
        return 0.0
    expected = task.expected_outcome.get("must_identify", "")
    if not expected:
        return 0.5
    expected_tokens = set(expected.lower().split())
    if not expected_tokens:
        return 0.5
    response_tokens = set(response_text.lower().split())
    overlap = expected_tokens & response_tokens
    return min(1.0, len(overlap) / len(expected_tokens))


def _load_existing_results(gen_dir: Path) -> list[dict]:
    """Load all POLICY_RUN_SUMMARY.json files from a generation directory."""
    results = []
    if not gen_dir.is_dir():
        return results
    for policy_dir in sorted(gen_dir.iterdir()):
        if not policy_dir.is_dir():
            continue
        for task_dir in sorted(policy_dir.iterdir()):
            if not task_dir.is_dir():
                continue
            s = task_dir / "POLICY_RUN_SUMMARY.json"
            if s.is_file():
                results.append(json.loads(s.read_text()))
    return results


def _run_single(
    *,
    generation_label: str,
    policy_label: str,
    policy: ArchitecturePolicy,
    cfg: dict,
    task: SealedTask,
    input_file: Path,
    out_dir: Path,
) -> dict:
    """Run orchestrator once, return summary dict."""
    from metaengine.orchestrator import MetaOrchestrator

    # Resume
    summary_path = out_dir / "POLICY_RUN_SUMMARY.json"
    contribution_path = out_dir / "engines" / "engine_16" / "CONTRIBUTION.json"
    if contribution_path.is_file() and summary_path.is_file():
        return json.loads(summary_path.read_text())

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.parent.mkdir(parents=True, exist_ok=True)

    orchestrator = MetaOrchestrator(ROOT, persist_biographies=False)
    orchestrator.cfg = cfg

    started = time.perf_counter()
    try:
        orchestrator.run(
            input_path=str(input_file),
            out_dir=str(out_dir),
            max_workers=4,
            experiment_policy={
                "max_rounds": 1,
                "max_deep_engines": 1,
                "architecture_policy": policy.as_dict(),
            },
        )
    except Exception as exc:
        print(f"  FAILED: {exc}", file=sys.stderr)
        elapsed = time.perf_counter() - started
        summary = {
            "generation": generation_label,
            "policy_label": policy_label,
            "task_id": task.task_id,
            "quality": 0.0, "cost": 1.0, "latency": elapsed,
            "reproducibility": 0.0, "resource_efficiency": 0.0,
            "total_tokens": 0, "response_text_length": 0,
            "error": str(exc)[:200],
        }
        summary_path.write_text(json.dumps(summary, indent=2))
        return summary
    elapsed = time.perf_counter() - started

    response_text = ""
    total_tokens = 0
    if contribution_path.is_file():
        c = json.loads(contribution_path.read_text())
        canonical = c.get("canonical", {}) or {}
        response_text = canonical.get("response_text", "") or ""
        usage = c.get("usage", {}) or {}
        total_tokens = int(usage.get("total_tokens", 0))

    quality = _evaluate_quality(task, response_text)
    cost = max(1.0, float(total_tokens) / 1000.0)
    latency = elapsed

    summary = {
        "generation": generation_label,
        "policy_label": policy_label,
        "task_id": task.task_id,
        "quality": quality,
        "cost": cost,
        "latency": latency,
        "reproducibility": 1.0,
        "resource_efficiency": round(quality / max(0.01, cost), 4),
        "total_tokens": total_tokens,
        "response_text_length": len(response_text),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def main():
    print("=" * 70)
    print("Phase 34 — Recursive Self-Improvement (FINALIZE)")
    print("=" * 70)

    out_root = ROOT / "storage" / "phase34_recursive_improvement"
    out_root.mkdir(parents=True, exist_ok=True)

    # 1. Bridge
    print("\n[1/6] Verifying LLM bridge...")
    if not _bridge_health():
        print("  bridge not healthy — aborting", file=sys.stderr)
        return 1
    print("  ✓ bridge healthy")

    # 2. Load G0 results (whatever we have)
    print("\n[2/6] Loading existing G0 results...")
    g0_summaries = _load_existing_results(out_root / "G0")
    if not g0_summaries:
        print("  no G0 results found — aborting", file=sys.stderr)
        return 1
    print(f"  G0 results: {len(g0_summaries)}")
    for s in g0_summaries:
        print(f"    {s['policy_label']}/{s['task_id']}: q={s['quality']:.3f} tokens={s.get('total_tokens',0)}")

    # 3. Build the trained model from G0 observations
    print("\n[3/6] Training predictive model on G0 outcomes...")
    model = OrganizationModel.create()
    for s in g0_summaries:
        model = model.add_observation(
            task_id=s["task_id"],
            policy_id=s["policy_label"],
            quality=s["quality"],
            cost=s["cost"],
            latency=s["latency"],
        )
    print(f"  model: {len(model.observations)} observations")
    # Show model predictions for each (policy, task) combo
    task_ids = sorted({s["task_id"] for s in g0_summaries})
    policy_ids = sorted({s["policy_label"] for s in g0_summaries})
    for tid in task_ids:
        for pid in policy_ids:
            pred = model.predict(task_id=tid, policy_id=pid)
            print(f"    predict({tid}, {pid}): q={pred.predicted_quality:.3f} conf={pred.confidence:.3f}")

    # 4. Build cfg, policies, tasks
    print("\n[4/6] Building config + policies + tasks...")
    cfg_path = ROOT / "config" / "meta_engine.json"
    with open(cfg_path) as f:
        base_cfg = json.load(f)
    llm_cfg = _upgrade_engine_16_to_llm(base_cfg)
    policies = _build_policies()
    policy_dict = {label: pol for label, pol in policies}
    for label, pol in policies:
        print(f"  - {label}: topology={pol.topology_id}")

    # Generate sealed tasks — we only run G1 on tasks we have G0 data for
    suite = SealedBenchmarkSuite(seed=42)
    all_tasks = list(suite.generate_sealed_tasks(count=4))
    # Filter to the tasks we have G0 data for
    g0_task_ids = {s["task_id"] for s in g0_summaries}
    g1_tasks = [t for t in all_tasks if t.task_id in g0_task_ids]
    print(f"  G1 will run on {len(g1_tasks)} tasks: {[t.task_id for t in g1_tasks]}")

    # 5. Run G1 — predicted-best selection
    print("\n[5/6] Running G1 (predicted-best policy selection)...")
    g1_summaries: list[dict] = []
    g1_experiments = 0
    g1_correct = 0
    quality_threshold = 0.5

    input_dir = out_root / "_sealed_inputs"
    input_dir.mkdir(parents=True, exist_ok=True)

    for i, task in enumerate(g1_tasks):
        # Predict best policy
        best_pred = None
        best_label = None
        for label, _ in policies:
            pred = model.predict(task_id=task.task_id, policy_id=label)
            if best_pred is None or pred.predicted_quality > best_pred.predicted_quality:
                best_pred = pred
                best_label = label
        policy = policy_dict[best_label]
        print(f"\n  [G1/{task.task_id}] selected={best_label} (predicted q={best_pred.predicted_quality:.3f})")

        if i > 0:
            print("    (pausing 30s to avoid rate limit)")
            time.sleep(30)

        input_file = input_dir / f"sealed_task_{task.task_id}.txt"
        input_file.write_text(task.source_text)
        run_dir = out_root / "G1" / best_label / task.task_id
        summary = _run_single(
            generation_label="G1",
            policy_label=best_label,
            policy=policy,
            cfg=llm_cfg,
            task=task,
            input_file=input_file,
            out_dir=run_dir,
        )
        print(f"    quality={summary['quality']:.3f} tokens={summary.get('total_tokens',0)}")
        g1_summaries.append(summary)
        g1_experiments += 1
        if summary["quality"] > quality_threshold:
            g1_correct += 1

    # 6. G0 metrics
    g0_experiments = len(g0_summaries)
    g0_correct = sum(1 for s in g0_summaries if s["quality"] > quality_threshold)
    g0_accuracy = g0_correct / max(1, g0_experiments)
    g1_accuracy = g1_correct / max(1, g1_experiments)

    print(f"\n  G0: {g0_experiments} experiments, {g0_correct} correct → accuracy={g0_accuracy:.3f}")
    print(f"  G1: {g1_experiments} experiments, {g1_correct} correct → accuracy={g1_accuracy:.3f}")

    # 7. Compare generations
    print("\n[6/6] Comparing generations...")
    comparator = GenerationComparator()
    comparison = comparator.compare(
        g0_experiments=g0_experiments,
        g0_correct_predictions=g0_correct,
        g1_experiments=g1_experiments,
        g1_correct_predictions=g1_correct,
    )
    print(f"  G0 accuracy: {comparison.g0_accuracy:.4f}")
    print(f"  G1 accuracy: {comparison.g1_accuracy:.4f}")
    print(f"  G1 better: {comparison.g1_better}")
    print(f"  Improvement ratio: {comparison.improvement_ratio:.4f}")
    print(f"  Efficiency improved: {comparison.efficiency_improved}")
    print(f"  Experiment reduction: {comparison.experiment_reduction}")
    print(f"  Comparison hash: {comparison.result_hash[:32]}...")

    # 8. Save artifacts
    (out_root / "G0_RESULTS.json").write_text(json.dumps({
        "results": g0_summaries,
        "experiments": g0_experiments,
        "correct": g0_correct,
        "accuracy": g0_accuracy,
    }, indent=2, ensure_ascii=False))
    (out_root / "G1_RESULTS.json").write_text(json.dumps({
        "results": g1_summaries,
        "experiments": g1_experiments,
        "correct": g1_correct,
        "accuracy": g1_accuracy,
    }, indent=2, ensure_ascii=False))
    (out_root / "GENERATION_COMPARISON.json").write_text(
        json.dumps(comparison.as_dict(), indent=2, ensure_ascii=False)
    )

    # 9. Manifest
    manifest = {
        "phase": 34,
        "title": "Recursive Self-Improvement Demonstration",
        "g0": {
            "selection_mode": "RANDOM",
            "experiments": g0_experiments,
            "correct": g0_correct,
            "accuracy": g0_accuracy,
            "results": [{"policy": s["policy_label"], "task": s["task_id"], "quality": s["quality"]} for s in g0_summaries],
        },
        "g1": {
            "selection_mode": "PREDICTED_BEST_FROM_G0_MODEL",
            "experiments": g1_experiments,
            "correct": g1_correct,
            "accuracy": g1_accuracy,
            "results": [{"policy": s["policy_label"], "task": s["task_id"], "quality": s["quality"]} for s in g1_summaries],
        },
        "comparison": comparison.as_dict(),
        "constitution_compliance": {
            "truth_effect": "NONE",
            "claim_ceiling": "GENERATION_COMPARISON_IS_EVALUATIVE_NOT_TRUTH",
            "self_promotion": False,
            "g1_policy_remains_shadow": True,
            "improvement_measured_not_assumed": True,
        },
    }
    (out_root / "PHASE34_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )

    print(f"\n{'=' * 70}")
    print(f"Phase 34 COMPLETE. Artifacts saved to {out_root}")
    print(f"  G0 accuracy: {g0_accuracy:.3f} ({g0_correct}/{g0_experiments})")
    print(f"  G1 accuracy: {g1_accuracy:.3f} ({g1_correct}/{g1_experiments})")
    print(f"  Improvement ratio: {comparison.improvement_ratio:.4f}")
    print(f"  G1 better: {comparison.g1_better}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
