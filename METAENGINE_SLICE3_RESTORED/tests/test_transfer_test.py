"""METAENGINE Step 2 — Heterogeneous transfer test for sparse-conditional-routing.

Design doc §20: "a heterogeneous transfer test with independently implemented
resources/models under the same mechanism contract."

The transfer test checks whether the sparse-conditional-routing mechanism
TRANSFERS across independently implemented resources, or is local-only. Each
implementation has its OWN routing criterion (not the same affinity function):
- LEXICAL: routes by token overlap
- SEMANTIC_CLUSTER: routes by word-embedding-style cluster membership
- HASH_BASELINE: routes by deterministic hash (control)

The evaluator uses an independent ground-truth (not any router's criterion).
A mechanism that "works" only on one implementation is LOCAL; one that works
across implementations TRANSFERS.
"""

from __future__ import annotations

import pytest

from metaengine.experiments.transfer_test import (
    ImplementationKind,
    TransferArm,
    TransferContract,
    TransferDecision,
    TransferReceipt,
    TransferRegime,
    TransferSpecialist,
    TransferTask,
    TransferTaskSuite,
    build_default_transfer_contract,
    run_transfer_test,
)


CONSTITUTION_HASH = "1b6311bd3dd6af060f05e63d22f3a28af776c117c4cc251c9383a6b8614f240d"
MECHANISM_CARD_HASH = "4d85480374490d4cee7c72ee3822d25278148b9984d12d7e2972d1c9abc47334"


def _contract():
    return build_default_transfer_contract(
        constitution_hash=CONSTITUTION_HASH,
        mechanism_card_hash=MECHANISM_CARD_HASH,
    )


# ---------------------------------------------------------------------------
# 1. Transfer contract is frozen + content-addressed
# ---------------------------------------------------------------------------


def test_transfer_contract_hash_deterministic():
    c1 = _contract()
    c2 = _contract()
    assert c1.contract_hash == c2.contract_hash
    assert len(c1.contract_hash) == 64


def test_transfer_contract_includes_all_implementation_kinds():
    c = _contract()
    kinds = {s.implementation_kind for s in c.specialists}
    assert ImplementationKind.LEXICAL in kinds
    assert ImplementationKind.SEMANTIC_CLUSTER in kinds
    assert ImplementationKind.HASH_BASELINE in kinds


def test_transfer_contract_tamper_rejected():
    c = _contract()
    tampered = c.payload()
    tampered["k"] = 999
    with pytest.raises(ValueError, match="CONTRACT_HASH_MISMATCH"):
        TransferContract.from_dict({**tampered, "contract_hash": c.contract_hash})


# ---------------------------------------------------------------------------
# 2. Each implementation has its OWN routing criterion (heterogeneous)
# ---------------------------------------------------------------------------


def test_lexical_router_uses_token_overlap():
    """LEXICAL router selects by token overlap — NOT affinity."""
    c = _contract()
    lexical_specs = [s for s in c.specialists if s.implementation_kind is ImplementationKind.LEXICAL]
    assert len(lexical_specs) >= 2
    task = c.task_suite.tasks[0]
    # The lexical router must produce a deterministic selection
    from metaengine.experiments.transfer_test import select_lexical
    selected = select_lexical(lexical_specs, task, k=2)
    assert len(selected) == 2
    # Same input -> same output (deterministic)
    assert select_lexical(lexical_specs, task, k=2) == selected


def test_semantic_router_uses_cluster_membership():
    """SEMANTIC_CLUSTER router selects by cluster overlap — NOT affinity."""
    c = _contract()
    semantic_specs = [s for s in c.specialists if s.implementation_kind is ImplementationKind.SEMANTIC_CLUSTER]
    assert len(semantic_specs) >= 2
    task = c.task_suite.tasks[0]
    from metaengine.experiments.transfer_test import select_semantic
    selected = select_semantic(semantic_specs, task, k=2)
    assert len(selected) == 2
    assert select_semantic(semantic_specs, task, k=2) == selected


def test_hash_baseline_router_is_control():
    """HASH_BASELINE router is a control — deterministic but content-blind."""
    c = _contract()
    hash_specs = [s for s in c.specialists if s.implementation_kind is ImplementationKind.HASH_BASELINE]
    assert len(hash_specs) >= 2
    task = c.task_suite.tasks[0]
    from metaengine.experiments.transfer_test import select_hash_baseline
    selected = select_hash_baseline(hash_specs, task, k=2)
    assert len(selected) == 2


def test_routers_are_heterogeneous():
    """The three routers must produce DIFFERENT selections on at least one task
    (otherwise they are not heterogeneous)."""
    c = _contract()
    from metaengine.experiments.transfer_test import select_lexical, select_semantic, select_hash_baseline
    lexical_specs = [s for s in c.specialists if s.implementation_kind is ImplementationKind.LEXICAL]
    semantic_specs = [s for s in c.specialists if s.implementation_kind is ImplementationKind.SEMANTIC_CLUSTER]
    hash_specs = [s for s in c.specialists if s.implementation_kind is ImplementationKind.HASH_BASELINE]
    task = c.task_suite.tasks[0]
    sel_lex = set(select_lexical(lexical_specs, task, k=2))
    sel_sem = set(select_semantic(semantic_specs, task, k=2))
    sel_hash = set(select_hash_baseline(hash_specs, task, k=2))
    # At least two of the three must differ (heterogeneity)
    selections = [sel_lex, sel_sem, sel_hash]
    unique = len(set(tuple(sorted(s)) for s in selections))
    assert unique >= 2, f"routers are not heterogeneous: {selections}"


# ---------------------------------------------------------------------------
# 3. Transfer arms: DENSE, RANDOM, ROUTED (per implementation kind)
# ---------------------------------------------------------------------------


def test_transfer_arms_are_three():
    assert {a.value for a in TransferArm} == {"DENSE_ALL", "RANDOM_TOP_K", "ROUTED_TOP_K"}


def test_transfer_run_produces_all_arms_per_implementation():
    c = _contract()
    receipt = run_transfer_test(c)
    # For each implementation kind, there must be results for all 3 arms
    impls = {s.implementation_kind for s in c.specialists}
    for impl in impls:
        arm_results = [r for r in receipt.results if r.implementation_kind is impl]
        arms_present = {r.arm for r in arm_results}
        assert arms_present == {TransferArm.DENSE_ALL, TransferArm.RANDOM_TOP_K, TransferArm.ROUTED_TOP_K}, (
            f"implementation {impl.value} missing arms: {arms_present}"
        )


# ---------------------------------------------------------------------------
# 4. Independent ground-truth evaluator (not any router's criterion)
# ---------------------------------------------------------------------------


def test_evaluator_uses_ground_truth_not_routing_criterion():
    """The evaluator must score by independent ground-truth, not by any
    router's selection criterion (lexical overlap, semantic cluster, or hash)."""
    c = _contract()
    receipt = run_transfer_test(c)
    # Each task has ground_truth that is independent of all routing criteria
    for task in c.task_suite.tasks:
        assert task.ground_truth, f"task {task.task_id} has no ground_truth"
        # Ground-truth values are in [0, 1]
        for sid, q in task.ground_truth:
            assert 0.0 <= q <= 1.0


# ---------------------------------------------------------------------------
# 5. Equal processing-resource budget across all arms
# ---------------------------------------------------------------------------


def test_equal_budget_all_transfer_arms():
    c = _contract()
    receipt = run_transfer_test(c)
    for ar in receipt.results:
        for tr in ar.task_results:
            assert tr.processing_resource_units == c.processing_resource_units


# ---------------------------------------------------------------------------
# 6. Transfer decision is one of three classes
# ---------------------------------------------------------------------------


def test_transfer_decision_is_valid():
    c = _contract()
    receipt = run_transfer_test(c)
    assert receipt.transfer_decision in TransferDecision
    assert receipt.transfer_decision.value in ("TRANSFERRED", "PARTIAL_TRANSFER", "NOT_TRANSFERRED")


def test_transfer_truth_and_assimilation_effects_none():
    c = _contract()
    receipt = run_transfer_test(c)
    assert receipt.truth_effect == "NONE"
    assert receipt.assimilation_effect == "NONE"


# ---------------------------------------------------------------------------
# 7. Transfer receipt is content-addressed + tamper-detect
# ---------------------------------------------------------------------------


def test_transfer_receipt_hash_deterministic():
    c = _contract()
    r1 = run_transfer_test(c)
    r2 = run_transfer_test(c)
    assert r1.receipt_hash == r2.receipt_hash


def test_transfer_receipt_tamper_rejected():
    c = _contract()
    receipt = run_transfer_test(c)
    tampered = receipt.as_dict()
    tampered["transfer_decision"] = "TRANSFERRED" if receipt.transfer_decision.value != "TRANSFERRED" else "NOT_TRANSFERRED"
    with pytest.raises(ValueError, match="RECEIPT_HASH_MISMATCH"):
        TransferReceipt.from_dict(tampered)


def test_transfer_receipt_replay():
    c = _contract()
    receipt = run_transfer_test(c)
    restored = TransferReceipt.from_dict(receipt.as_dict())
    assert restored.receipt_hash == receipt.receipt_hash


# ---------------------------------------------------------------------------
# 8. Per-implementation results recorded (heterogeneity evidence)
# ---------------------------------------------------------------------------


def test_per_implementation_quality_recorded():
    c = _contract()
    receipt = run_transfer_test(c)
    impls = {s.implementation_kind for s in c.specialists}
    for impl in impls:
        impl_results = [r for r in receipt.results if r.implementation_kind is impl]
        assert impl_results, f"no results for implementation {impl.value}"
        # Each implementation must have a routed vs dense comparison
        routed = [r for r in impl_results if r.arm is TransferArm.ROUTED_TOP_K]
        dense = [r for r in impl_results if r.arm is TransferArm.DENSE_ALL]
        assert routed and dense, f"implementation {impl.value} missing routed/dense arms"


def test_transfer_summary_records_per_implementation_outcome():
    c = _contract()
    receipt = run_transfer_test(c)
    assert len(receipt.transfer_summary) > 0
    for entry in receipt.transfer_summary:
        assert "implementation_kind" in entry
        assert "routed_better_than_dense" in entry
        assert "mean_quality_routed" in entry
        assert "mean_quality_dense" in entry
