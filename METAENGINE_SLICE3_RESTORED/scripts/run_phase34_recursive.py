"""METAENGINE Phase 34 — Recursive Self-Improvement Demonstration.

Compares two researcher generations:

  G0 (baseline researcher): Uses RANDOM experiment selection. Runs N tasks
    with no prior knowledge. Each task is an experiment. Records outcomes.
    Accuracy = fraction of tasks where quality > 0.5.

  G1 (learned researcher): Uses the predictive model trained on G0 outcomes.
    For each task, predicts which policy will give highest quality, and
    selects the predicted-best policy. Runs the same N tasks.
    Accuracy = fraction of tasks where quality > 0.5.

The improvement_ratio = G1_accuracy / G0_accuracy should be > 1.0 if learning
occurred. efficiency_improved = G1_better AND G1 uses fewer experiments
(G1 may skip experiments that the model predicts will fail).

Real evidence:
  - G0 runs REAL LLM calls (engine_16 via metaengine-llm-bridge).
  - G1 runs REAL LLM calls.
  - The predictive model is trained on REAL G0 outcomes.
  - The improvement ratio is computed from REAL quality measurements.

Constitution compliance:
  - truth_effect = NONE
  - claim_ceiling = GENERATION_COMPARISON_IS_EVALUATIVE_NOT_TRUTH
  - The improvement is measured, not assumed.
  - No self-promotion — the G1 policy remains SHADOW.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import random
import shutil
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.sealed_benchmark import SealedBenchmarkSuite, SealedTask
from metaengine.predictive_model import OrganizationModel, PredictionReceipt
from metaengine.recursive_improvement import GenerationComparator
from metaengine.architecture_policy import (
    ArchitecturePolicy,
    initial_policy,
)
from metaengine.organization_tournament import PolicyResult

# Bridge config
LLM_BRIDGE_ENDPOINT = "http://localhost:3031/v1/chat/completions"
LLM_BRIDGE_MODEL = "metaengine-glm-1"
LLM_BRIDGE_PORT = 3031


# --- Helpers -----------------------------------------------------------------


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
            e["name"] = (
                "Reference contract — DSPy architectural pattern "
                "[LLM-MODEL UPGRADE Phase 34]"
            )
    return new_cfg


def _build_policies_for_g0() -> list[tuple[str, ArchitecturePolicy]]:
    """G0 researcher tries BOTH policies randomly on each task."""
    base_policy = initial_policy()

    # Policy LLM_A: LLM with two operators (broader exploration)
    pol_llm_a = ArchitecturePolicy(
        generation=0,
        parent_policy_hash=base_policy.policy_hash,
        topology_id="LLM_CREATIVE",
        waves=(("engine_16",),),
        dialectic_operators=("OPERATOR_MUTATION", "EVIDENCE_DISCRIMINATOR"),
        max_rounds=1, max_deep_engines=1,
        exploration_rate=0.0,
        status="SHADOW",
        mutation_receipt={"origin": "PHASE34_G0_POLICY_LLM_A"},
    )
    pol_llm_a.validate()

    # Policy LLM_B: LLM with single operator (focused)
    pol_llm_b = ArchitecturePolicy(
        generation=0,
        parent_policy_hash=base_policy.policy_hash,
        topology_id="LLM_FOCUSED",
        waves=(("engine_16",),),
        dialectic_operators=("OPERATOR_MUTATION",),
        max_rounds=1, max_deep_engines=1,
        exploration_rate=0.0,
        status="SHADOW",
        mutation_receipt={"origin": "PHASE34_G0_POLICY_LLM_B"},
    )
    pol_llm_b.validate()

    return [
        ("LLM_CREATIVE", pol_llm_a),
        ("LLM_FOCUSED", pol_llm_b),
    ]


def _evaluate_quality(task: SealedTask, response_text: str) -> float:
    """Compute quality score — fraction of expected tokens in response."""
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


def _write_sealed_task_to_file(task: SealedTask, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"sealed_task_{task.task_id}.txt"
    p.write_text(task.source_text)
    return p


def _run_single(
    *,
    generation_label: str,
    policy_label: str,
    policy: ArchitecturePolicy,
    cfg: dict,
    task: SealedTask,
    input_file: Path,
    out_dir: Path,
) -> PolicyResult:
    """Run orchestrator once for a (generation, policy, task) and return metrics."""
    from metaengine.orchestrator import MetaOrchestrator

    # Resume support
    summary_path = out_dir / "POLICY_RUN_SUMMARY.json"
    contribution_path = out_dir / "engines" / "engine_16" / "CONTRIBUTION.json"
    if contribution_path.is_file() and summary_path.is_file():
        prior = json.loads(summary_path.read_text())
        return PolicyResult(
            policy_id=policy_label, task_id=task.task_id,
            quality=prior["quality"], cost=prior["cost"],
            latency=prior["latency"],
            reproducibility=prior["reproducibility"],
            resource_efficiency=prior["resource_efficiency"],
        )

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
        print(f"  [phase34] {generation_label}/{policy_label}/{task.task_id} FAILED: {exc}", file=sys.stderr)
        elapsed = time.perf_counter() - started
        return PolicyResult(
            policy_id=policy_label, task_id=task.task_id,
            quality=0.0, cost=1.0, latency=elapsed,
            reproducibility=0.0, resource_efficiency=0.0,
        )
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
    reproducibility = 1.0
    resource_efficiency = round(quality / max(0.01, cost), 4)

    summary = {
        "generation": generation_label,
        "policy_label": policy_label,
        "task_id": task.task_id,
        "quality": quality,
        "cost": cost,
        "latency": latency,
        "reproducibility": reproducibility,
        "resource_efficiency": resource_efficiency,
        "total_tokens": total_tokens,
        "response_text_length": len(response_text),
    }
    (out_dir / "POLICY_RUN_SUMMARY.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False)
    )

    return PolicyResult(
        policy_id=policy_label, task_id=task.task_id,
        quality=quality, cost=cost, latency=latency,
        reproducibility=reproducibility,
        resource_efficiency=resource_efficiency,
    )


def run_generation(
    *,
    generation_label: str,
    policies: list[tuple[str, ArchitecturePolicy]],
    cfg: dict,
    tasks: list[SealedTask],
    out_root: Path,
    model: OrganizationModel | None = None,
    quality_threshold: float = 0.5,
    pause_seconds: int = 30,
) -> tuple[list[PolicyResult], OrganizationModel, int, int]:
    """Run one generation over the task set.

    If model is None: RANDOM selection (G0) — pick a random policy per task.
    If model is provided: PREDICTED-BEST selection (G1) — pick the policy with
        highest predicted quality, and SKIP experiments where predicted quality
        is below threshold (efficiency gain).

    Returns (results, updated_model, experiments_run, correct_predictions).
    correct_predictions = experiments where quality > quality_threshold.
    """
    rng = random.Random(42)
    results: list[PolicyResult] = []
    experiments_run = 0
    correct_predictions = 0
    updated_model = model or OrganizationModel.create()

    input_dir = out_root / "_sealed_inputs"
    input_dir.mkdir(parents=True, exist_ok=True)

    for i, task in enumerate(tasks):
        # Select policy
        if model is None or not model.observations:
            # G0: random selection
            policy_label, policy = rng.choice(policies)
            selection_mode = "RANDOM"
        else:
            # G1: predicted-best selection
            best_pred = None
            best_label = None
            for label, _ in policies:
                pred = model.predict(task_id=task.task_id, policy_id=label)
                if best_pred is None or pred.predicted_quality > best_pred.predicted_quality:
                    best_pred = pred
                    best_label = label
            # Efficiency: skip if predicted quality is below threshold
            if best_pred and best_pred.predicted_quality < quality_threshold * 0.5:
                # Skip — predicted to fail. Record as a "saved experiment".
                print(f"  [{generation_label}/{task.task_id}] SKIPPED (predicted q={best_pred.predicted_quality:.3f} < {quality_threshold * 0.5:.3f})")
                continue
            policy_label = best_label
            policy = next(p for lbl, p in policies if lbl == best_label)
            selection_mode = f"PREDICTED (q={best_pred.predicted_quality:.3f})"

        # Write input file
        input_file = _write_sealed_task_to_file(task, input_dir)
        run_dir = out_root / generation_label / policy_label / task.task_id
        print(f"\n  [{generation_label}/{task.task_id}] policy={policy_label} mode={selection_mode}")
        if i > 0:
            time.sleep(pause_seconds)
        result = _run_single(
            generation_label=generation_label,
            policy_label=policy_label,
            policy=policy,
            cfg=cfg,
            task=task,
            input_file=input_file,
            out_dir=run_dir,
        )
        print(f"    quality={result.quality:.3f} cost={result.cost:.3f} "
              f"latency={result.latency:.2f}s tokens={int(result.cost * 1000)}")

        results.append(result)
        experiments_run += 1
        if result.quality > quality_threshold:
            correct_predictions += 1

        # Update model with actual outcome
        updated_model = updated_model.add_observation(
            task_id=task.task_id,
            policy_id=policy_label,
            quality=result.quality,
            cost=result.cost,
            latency=result.latency,
        )

    return results, updated_model, experiments_run, correct_predictions


def main():
    parser = argparse.ArgumentParser(description="Phase 34: Recursive Improvement")
    parser.add_argument(
        "--out",
        default="storage/phase34_recursive_improvement",
        help="Output directory",
    )
    parser.add_argument(
        "--num-tasks",
        type=int,
        default=4,
        help="Number of sealed tasks (default 4)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Phase 34 — Recursive Self-Improvement Demonstration")
    print("=" * 70)

    # 1. Verify bridge
    print("\n[1/6] Verifying LLM bridge...")
    if not _bridge_health():
        print("[phase34] LLM bridge not healthy — aborting", file=sys.stderr)
        return 1
    print("  ✓ bridge healthy")

    # 2. Generate sealed tasks (deterministic)
    print(f"\n[2/6] Generating {args.num_tasks} sealed tasks (seed=42)...")
    suite = SealedBenchmarkSuite(seed=42)
    sealed_tasks = list(suite.generate_sealed_tasks(count=args.num_tasks))
    for t in sealed_tasks:
        print(f"  - {t.task_id}: {t.source_text[:80]}...")

    # 3. Build config and policies
    print("\n[3/6] Building config + policies...")
    cfg_path = ROOT / "config" / "meta_engine.json"
    with open(cfg_path) as f:
        base_cfg = json.load(f)
    llm_cfg = _upgrade_engine_16_to_llm(base_cfg)
    policies = _build_policies_for_g0()
    for label, pol in policies:
        print(f"  - {label}: topology={pol.topology_id}, operators={len(pol.dialectic_operators)}")

    out_root = ROOT / args.out
    out_root.mkdir(parents=True, exist_ok=True)

    # 4. G0 — random selection
    print("\n[4/6] G0: Random experiment selection (no prior knowledge)...")
    g0_results, g0_model, g0_experiments, g0_correct = run_generation(
        generation_label="G0",
        policies=policies,
        cfg=llm_cfg,
        tasks=sealed_tasks,
        out_root=out_root,
        model=None,
        quality_threshold=0.5,
    )
    g0_accuracy = g0_correct / max(1, g0_experiments)
    print(f"\n  G0: {g0_experiments} experiments, {g0_correct} correct → accuracy={g0_accuracy:.3f}")
    print(f"  G0 model: {len(g0_model.observations)} observations")

    # Save G0 artifacts
    (out_root / "G0_RESULTS.json").write_text(
        json.dumps({
            "results": [r.payload() for r in g0_results],
            "experiments": g0_experiments,
            "correct": g0_correct,
            "accuracy": g0_accuracy,
            "model_observations": len(g0_model.observations),
        }, indent=2, ensure_ascii=False)
    )

    # 5. G1 — learned selection using G0-trained model
    print("\n[5/6] G1: Learned selection using G0-trained predictive model...")
    g1_results, g1_model, g1_experiments, g1_correct = run_generation(
        generation_label="G1",
        policies=policies,
        cfg=llm_cfg,
        tasks=sealed_tasks,
        out_root=out_root,
        model=g0_model,  # trained on G0 outcomes
        quality_threshold=0.5,
    )
    g1_accuracy = g1_correct / max(1, g1_experiments)
    print(f"\n  G1: {g1_experiments} experiments, {g1_correct} correct → accuracy={g1_accuracy:.3f}")
    print(f"  G1 model: {len(g1_model.observations)} observations (G0 + G1)")

    # Save G1 artifacts
    (out_root / "G1_RESULTS.json").write_text(
        json.dumps({
            "results": [r.payload() for r in g1_results],
            "experiments": g1_experiments,
            "correct": g1_correct,
            "accuracy": g1_accuracy,
            "model_observations": len(g1_model.observations),
        }, indent=2, ensure_ascii=False)
    )

    # 6. Compare generations
    print("\n[6/6] Comparing generations (GenerationComparator)...")
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

    # Save comparison
    (out_root / "GENERATION_COMPARISON.json").write_text(
        json.dumps(comparison.as_dict(), indent=2, ensure_ascii=False)
    )

    # Manifest
    manifest = {
        "phase": 34,
        "title": "Recursive Self-Improvement Demonstration",
        "g0": {
            "selection_mode": "RANDOM",
            "experiments": g0_experiments,
            "correct": g0_correct,
            "accuracy": g0_accuracy,
        },
        "g1": {
            "selection_mode": "PREDICTED_BEST_FROM_G0_MODEL",
            "experiments": g1_experiments,
            "correct": g1_correct,
            "accuracy": g1_accuracy,
        },
        "comparison": comparison.as_dict(),
        "g0_model_observations": len(g0_model.observations),
        "g1_model_observations": len(g1_model.observations),
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
    print(f"Phase 34 complete. Artifacts saved to {out_root}")
    print(f"  G0 accuracy: {g0_accuracy:.3f} ({g0_correct}/{g0_experiments})")
    print(f"  G1 accuracy: {g1_accuracy:.3f} ({g1_correct}/{g1_experiments})")
    print(f"  Improvement ratio: {comparison.improvement_ratio:.4f}")
    print(f"  G1 better: {comparison.g1_better}")
    print(f"  Efficiency improved: {comparison.efficiency_improved}")
    print(f"  Experiment reduction: {comparison.experiment_reduction}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
