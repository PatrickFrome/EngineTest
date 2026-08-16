"""METAENGINE CLI — with Slice 5 Gate Global Integration.

The `run` command now REQUIRES a --receipt argument pointing to a valid
DevelopmentEvolutionReviewReceipt JSON file. Before the orchestrator runs,
the development transition gate is checked:

1. Receipt file exists and loads.
2. Receipt integrity is valid (hash matches).
3. Receipt snapshots match the current project state (constitution/library/policy).
4. Receipt decision allows the next step.

After a successful run, a `stage_gate_summary.json` is produced in the output
directory, recording that the gate was enforced and the run completed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .orchestrator import MetaOrchestrator
from .routing import CapabilityRouter
from .replication import replicate_run
from .biographies import EngineBiographyStore
from .topology import TOPOLOGIES
from .frontier_control_plane import PATTERN_SOURCES
from .parallel_ecology import (
    ParallelExperimentalEcology,
    ExperimentCase,
    write_variants,
    single_ablation_cases,
    pair_ablation_cases,
    topology_cases,
)
from .architecture_policy import PolicyStore
from .worldbench import EvolutionCampaign
from .util import canonical_hash, write_json
from .devfabric.development_review import (
    DevelopmentEvolutionReviewReceipt,
    load_bootstrap_review_context,
    verify_receipt_integrity,
)
from .devfabric.development_gate import (
    DevelopmentTransitionRequest,
    verify_development_transition,
)


# ---------------------------------------------------------------------------
# Gate enforcement
# ---------------------------------------------------------------------------


class GateCheckError(RuntimeError):
    """Raised when the development review gate check fails."""


def check_development_gate(
    *,
    receipt_path: str | None,
    root: str | Path,
    previous_step_id: str = "METAENGINE-1-SLICE-4",
    next_step_id: str = "METAENGINE-1-SLICE-5",
) -> DevelopmentTransitionRequest:
    """Check the development review gate before allowing a run.

    Raises GateCheckError if the gate check fails.
    Returns the DevelopmentTransitionRequest if the gate is passed.
    """
    root = Path(root).resolve()

    # 1. Receipt path is required
    if receipt_path is None:
        raise GateCheckError(
            "RECEIPT_REQUIRED: --receipt is required. Provide a path to a valid "
            "DevelopmentEvolutionReviewReceipt JSON file."
        )

    # 2. Receipt file must exist
    receipt_file = Path(receipt_path)
    if not receipt_file.is_file():
        raise GateCheckError(
            f"RECEIPT_FILE_NOT_FOUND: {receipt_path}"
        )

    # 3. Load and verify receipt
    try:
        receipt_data = json.loads(receipt_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise GateCheckError(f"RECEIPT_LOAD_FAILED: {exc}") from exc

    try:
        receipt = DevelopmentEvolutionReviewReceipt.from_dict(receipt_data)
    except ValueError as exc:
        raise GateCheckError(f"RECEIPT_INVALID: {exc}") from exc

    # 4. Verify receipt integrity (hash matches)
    integrity = verify_receipt_integrity(receipt)
    if not integrity.valid:
        raise GateCheckError(f"RECEIPT_INVALID: {integrity.reason}")

    # 5. Load current project context (snapshots)
    try:
        context = load_bootstrap_review_context(root)
    except Exception as exc:
        raise GateCheckError(f"CONTEXT_LOAD_FAILED: {exc}") from exc

    # 6. Verify development transition
    request = DevelopmentTransitionRequest(
        previous_step_id=previous_step_id,
        previous_step_commit=receipt.completed_step_commit,
        next_step_id=next_step_id,
        current_context=context,
        receipt=receipt,
    )
    result = verify_development_transition(request)
    if not result.allowed:
        raise GateCheckError(
            f"GATE_REJECTED: {result.reason} "
            f"(receipt_hash={result.receipt_hash})"
        )

    return request


# ---------------------------------------------------------------------------
# Stage gate summary
# ---------------------------------------------------------------------------


STAGE_GATE_VERSION = "METAENGINE-STAGE-GATE-SUMMARY-1"


def produce_stage_gate_summary(
    run_result: dict[str, Any],
    *,
    receipt_hash: str,
    root: str | Path,
    previous_step_id: str = "METAENGINE-1-SLICE-4",
    next_step_id: str = "METAENGINE-1-SLICE-5",
) -> dict[str, Any]:
    """Produce a stage gate summary after a successful run.

    Records that the gate was enforced, the run completed, and the key
    constitutional invariants held.
    """
    summary = {
        "stage_gate_version": STAGE_GATE_VERSION,
        "gate_enforced": True,
        "previous_step_id": previous_step_id,
        "next_step_id": next_step_id,
        "receipt_hash": receipt_hash,
        "meta_run_id": run_result.get("meta_run_id"),
        "run_status": run_result.get("status"),
        "input_hash": run_result.get("input_hash"),
        "telemetry_hash": run_result.get("telemetry_hash"),
        "constitutional_invariants": {
            "majority_vote_used": run_result.get("majority_vote_used", False),
            "derived_truth_promotion_violations": run_result.get(
                "derived_truth_promotion_violations", 0
            ),
            "architecture_mutations": run_result.get("architecture_mutations", 0),
            "truth_effect": "NONE",
        },
        "claim_ceiling": run_result.get("claim_ceiling", "NATIVE_CLAIM_CEILINGS_PRESERVED"),
    }
    summary["gate_summary_hash"] = canonical_hash(summary)
    return summary


# ---------------------------------------------------------------------------
# CLI main
# ---------------------------------------------------------------------------


def main():
    p = argparse.ArgumentParser(prog="destruktion-meta16")
    sub = p.add_subparsers(dest="cmd", required=True)

    # run: now requires --receipt
    s = sub.add_parser("run")
    s.add_argument("input")
    s.add_argument("--out", required=True)
    s.add_argument("--max-workers", type=int, default=16)
    s.add_argument(
        "--receipt",
        required=True,
        help="Path to a valid DevelopmentEvolutionReviewReceipt JSON file. "
        "The development review gate is checked before the orchestrator runs.",
    )
    s.add_argument(
        "--previous-step",
        default="METAENGINE-1-SLICE-4",
        help="Previous step ID for the development transition check.",
    )
    s.add_argument(
        "--next-step",
        default="METAENGINE-1-SLICE-5",
        help="Next step ID for the development transition check.",
    )

    r = sub.add_parser("route")
    r.add_argument("input")
    rp = sub.add_parser("replicate")
    rp.add_argument("run_dir")
    rp.add_argument("--backend", choices=["supabase"], default="supabase")
    sub.add_parser("engines")
    sub.add_parser("capabilities")
    sub.add_parser("biographies")
    sub.add_parser("topologies")
    sub.add_parser("frontier-patterns")
    pb = sub.add_parser("parallel-benchmark")
    pb.add_argument("inputs", nargs="+")
    pb.add_argument("--out", required=True)
    pb.add_argument("--world-workers", type=int, default=8)
    pb.add_argument("--inner-workers", type=int, default=2)
    pb.add_argument("--batch-size", type=int, default=4)
    pw = sub.add_parser("parallel-worlds")
    pw.add_argument("input")
    pw.add_argument("--out", required=True)
    pw.add_argument("--worlds", type=int, default=24)
    pw.add_argument("--world-workers", type=int, default=8)
    pw.add_argument("--inner-workers", type=int, default=2)
    pw.add_argument("--batch-size", type=int, default=4)
    pa = sub.add_parser("parallel-ablation")
    pa.add_argument("input")
    pa.add_argument("--out", required=True)
    pa.add_argument("--order", type=int, choices=[1, 2], default=1)
    pa.add_argument("--limit", type=int)
    pa.add_argument("--world-workers", type=int, default=8)
    pa.add_argument("--inner-workers", type=int, default=2)
    pa.add_argument("--batch-size", type=int, default=4)
    pt = sub.add_parser("parallel-topologies")
    pt.add_argument("input")
    pt.add_argument("--out", required=True)
    pt.add_argument("--repeats", type=int, default=4)
    pt.add_argument("--world-workers", type=int, default=8)
    pt.add_argument("--inner-workers", type=int, default=2)
    pt.add_argument("--batch-size", type=int, default=4)
    ev = sub.add_parser("evolve")
    ev.add_argument("--out", required=True)
    ev.add_argument("--generations", type=int, default=3)
    ev.add_argument("--candidates", type=int, default=24)
    ev.add_argument("--world-workers", type=int, default=8)
    ev.add_argument("--seeds", type=int, nargs="+", default=[17, 43])
    ev.add_argument("--cases-per-suite", type=int, default=8)
    sub.add_parser("active-policy")
    rb = sub.add_parser("rollback-policy")
    rb.add_argument("policy_hash")
    rb.add_argument("--reason", required=True)

    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]

    if a.cmd == "run":
        # --- GATE ENFORCEMENT (Slice 5) ---
        try:
            request = check_development_gate(
                receipt_path=a.receipt,
                root=root,
                previous_step_id=a.previous_step,
                next_step_id=a.next_step,
            )
        except GateCheckError as exc:
            print(f"GATE_CHECK_FAILED: {exc}", file=sys.stderr)
            sys.exit(2)

        # --- ORCHESTRATOR RUN ---
        result = MetaOrchestrator(root).run(a.input, a.out, a.max_workers)

        # --- STAGE GATE SUMMARY (Slice 5) ---
        summary = produce_stage_gate_summary(
            result,
            receipt_hash=request.receipt.receipt_hash,
            root=root,
            previous_step_id=a.previous_step,
            next_step_id=a.next_step,
        )
        out_dir = Path(a.out)
        write_json(out_dir / "stage_gate_summary.json", summary)

        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif a.cmd == "route":
        print(json.dumps(CapabilityRouter(root).plan(a.input), ensure_ascii=False, indent=2))
    elif a.cmd == "replicate":
        print(json.dumps([replicate_run(a.run_dir, a.backend)], ensure_ascii=False, indent=2))
    elif a.cmd == "engines":
        print((root / "config/meta_engine.json").read_text())
    elif a.cmd == "capabilities":
        print((root / "config/capability_registry.json").read_text())
    elif a.cmd == "biographies":
        print(json.dumps(EngineBiographyStore(root).snapshot(), ensure_ascii=False, indent=2))
    elif a.cmd == "topologies":
        print(json.dumps(TOPOLOGIES, ensure_ascii=False, indent=2))
    elif a.cmd == "frontier-patterns":
        print(json.dumps(PATTERN_SOURCES, ensure_ascii=False, indent=2))
    elif a.cmd == "parallel-benchmark":
        cases = [
            ExperimentCase(f"bench_{i:03d}", str(Path(x).resolve()), "BENCHMARK", {"freeze_biography": True, "cache_mode": "isolated"})
            for i, x in enumerate(a.inputs)
        ]
        print(json.dumps(ParallelExperimentalEcology(root).run(cases, a.out, a.world_workers, a.inner_workers, a.batch_size)["summary"], ensure_ascii=False, indent=2))
    elif a.cmd == "parallel-worlds":
        variants = write_variants(a.input, Path(a.out).with_name(Path(a.out).name + "_variants"), a.worlds)
        cases = [ExperimentCase(f"world_{i:03d}", str(p), "PERTURBATION_WORLD", {"freeze_biography": True, "cache_mode": "isolated"}) for i, p in enumerate(variants)]
        print(json.dumps(ParallelExperimentalEcology(root).run(cases, a.out, a.world_workers, a.inner_workers, a.batch_size)["summary"], ensure_ascii=False, indent=2))
    elif a.cmd == "parallel-ablation":
        cases = single_ablation_cases(a.input) if a.order == 1 else pair_ablation_cases(a.input, a.limit)
        print(json.dumps(ParallelExperimentalEcology(root).run(cases, a.out, a.world_workers, a.inner_workers, a.batch_size)["summary"], ensure_ascii=False, indent=2))
    elif a.cmd == "parallel-topologies":
        print(json.dumps(ParallelExperimentalEcology(root).run(topology_cases(a.input, a.repeats), a.out, a.world_workers, a.inner_workers, a.batch_size)["summary"], ensure_ascii=False, indent=2))
    elif a.cmd == "evolve":
        print(json.dumps(EvolutionCampaign(root).run(a.out, a.generations, a.candidates, a.world_workers, tuple(a.seeds), a.cases_per_suite), ensure_ascii=False, indent=2))
    elif a.cmd == "active-policy":
        print(json.dumps(PolicyStore(root).active().as_dict(), ensure_ascii=False, indent=2))
    elif a.cmd == "rollback-policy":
        print(json.dumps(PolicyStore(root).rollback(a.policy_hash, a.reason).as_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
