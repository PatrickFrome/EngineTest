"""METAENGINE Step 4 — Runtime D6-G1 guard instrumentation tests.

The guard ``assert_d6_g1_shadow_only`` was added in Task 26, but it is a
function that must be called explicitly. Step 4 instruments it into
``build_adaptation_receipt`` so that it is called AUTOMATICALLY at receipt
creation time — making it impossible to create an AdaptationReceipt with a
canonical-activation status.

This closes W7 (D6-G1 shadow-only — policy + code, but no runtime enforcement).
"""

from __future__ import annotations

import pytest

from metaengine.devfabric.federation.adaptation import (
    AdaptationReceipt,
    ConcurrencyDecision,
    FinalizedEpochMetrics,
    build_adaptation_receipt,
    assert_d6_g1_shadow_only,
    D6_G1_FORBIDDEN_CANONICAL_STATUSES,
    D6_G1_SHADOW_ONLY_STATUSES,
)
from metaengine.devfabric.federation.types import SlotId
from metaengine.devfabric.federation.roles import load_role_genome


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def project_root():
    """The restored tree root (has chat_federation/ROLE_GENOMES/)."""
    from pathlib import Path
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def empty_metrics_window():
    """A minimal valid metrics window (empty — produces HOLD_INSUFFICIENT_EVIDENCE)."""
    return ()


@pytest.fixture
def current_policy_hash():
    return "1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48"


# ---------------------------------------------------------------------------
# 1. build_adaptation_receipt auto-calls the guard (impossible to create canonical receipt)
# ---------------------------------------------------------------------------


def test_build_receipt_with_shadow_status_succeeds(project_root, empty_metrics_window, current_policy_hash):
    """Building a receipt that produces a shadow-only status must succeed."""
    receipt = build_adaptation_receipt(
        metrics_window=empty_metrics_window,
        current_policy_hash=current_policy_hash,
        current_producer_concurrency=4,
        role_proposals=(),
        telemetry_schema_hash="0" * 64,
    )
    # The status must be a shadow-only status (not canonical)
    assert receipt.status in D6_G1_SHADOW_ONLY_STATUSES


def test_build_receipt_never_produces_canonical_status(project_root, empty_metrics_window, current_policy_hash):
    """The build function must NEVER produce a canonical-activation status.
    Even with various inputs, the status is always shadow-only or hold."""
    for concurrency in (2, 3, 4, 5, 6):  # valid range is 2-6
        receipt = build_adaptation_receipt(
            metrics_window=empty_metrics_window,
            current_policy_hash=current_policy_hash,
            current_producer_concurrency=concurrency,
            role_proposals=(),
            telemetry_schema_hash="0" * 64,
        )
        assert receipt.status not in D6_G1_FORBIDDEN_CANONICAL_STATUSES, (
            f"build produced forbidden status {receipt.status} for concurrency={concurrency}"
        )


# ---------------------------------------------------------------------------
# 2. Guard is called at build time (instrumentation test)
# ---------------------------------------------------------------------------


def test_guard_is_called_at_build_time(monkeypatch, project_root, empty_metrics_window, current_policy_hash):
    """The guard function must be called during build_adaptation_receipt.

    We monkeypatch assert_d6_g1_shadow_only to track calls. If the build
    function does not call the guard, this test fails — proving the
    instrumentation is in place.
    """
    called = {"count": 0}

    original_guard = assert_d6_g1_shadow_only

    def tracking_guard(receipt):
        called["count"] += 1
        original_guard(receipt)

    # Monkeypatch the guard in the module where build_adaptation_receipt looks it up
    import metaengine.devfabric.federation.adaptation as adaptation_mod
    monkeypatch.setattr(adaptation_mod, "assert_d6_g1_shadow_only", tracking_guard)

    build_adaptation_receipt(
        metrics_window=empty_metrics_window,
        current_policy_hash=current_policy_hash,
        current_producer_concurrency=4,
        role_proposals=(),
        telemetry_schema_hash="0" * 64,
    )

    assert called["count"] == 1, (
        "assert_d6_g1_shadow_only was NOT called during build_adaptation_receipt — "
        "the guard is not instrumented at build time"
    )


def test_guard_blocks_canonical_status_at_build(monkeypatch, project_root, empty_metrics_window, current_policy_hash):
    """If the guard is monkeypatched to raise, build must propagate the error.

    This proves the guard is in the build path (not just callable externally).
    """
    import metaengine.devfabric.federation.adaptation as adaptation_mod

    def raising_guard(receipt):
        raise ValueError("D6_G1_SHADOW_ONLY_VIOLATION: blocked by test")

    monkeypatch.setattr(adaptation_mod, "assert_d6_g1_shadow_only", raising_guard)

    with pytest.raises(ValueError, match="D6_G1_SHADOW_ONLY_VIOLATION"):
        build_adaptation_receipt(
            metrics_window=empty_metrics_window,
            current_policy_hash=current_policy_hash,
            current_producer_concurrency=4,
            role_proposals=(),
            telemetry_schema_hash="0" * 64,
        )


# ---------------------------------------------------------------------------
# 3. Guard is also called in verify_shadow_receipt (replay path)
# ---------------------------------------------------------------------------


def test_verify_shadow_receipt_calls_guard(monkeypatch, project_root, empty_metrics_window, current_policy_hash):
    """verify_shadow_receipt must also call the guard on replay."""
    called = {"count": 0}
    original_guard = assert_d6_g1_shadow_only

    def tracking_guard(receipt):
        called["count"] += 1

    import metaengine.devfabric.federation.adaptation as adaptation_mod
    monkeypatch.setattr(adaptation_mod, "assert_d6_g1_shadow_only", tracking_guard)

    receipt = build_adaptation_receipt(
        metrics_window=empty_metrics_window,
        current_policy_hash=current_policy_hash,
        current_producer_concurrency=4,
        role_proposals=(),
        telemetry_schema_hash="0" * 64,
    )

    # verify_shadow_receipt should call the guard on the rebuilt receipt
    from metaengine.devfabric.federation.adaptation import verify_shadow_receipt
    try:
        verify_shadow_receipt(
            receipt,
            metrics_window=empty_metrics_window,
            current_policy_hash=current_policy_hash,
            current_producer_concurrency=4,
            role_proposals=(),
            telemetry_schema_hash="0" * 64,
        )
    except Exception:
        pass  # verify may fail for other reasons; we only care about guard call

    assert called["count"] >= 2, (
        "assert_d6_g1_shadow_only was not called during verify_shadow_receipt — "
        "the guard is not instrumented on the replay path"
    )


# ---------------------------------------------------------------------------
# 4. All shadow-only statuses are valid build outputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("expected_status", sorted(D6_G1_SHADOW_ONLY_STATUSES))
def test_shadow_only_status_is_valid_build_output(expected_status):
    """Each shadow-only status must be a valid build output (not rejected by guard)."""
    # Construct a receipt with this status and verify the guard accepts it
    receipt = AdaptationReceipt(
        protocol_version="D6.ADAPTATION.1",
        adaptation_input_hash="0" * 64,
        adaptation_receipt_hash="0" * 64,
        evidence_finalization_hashes=(),
        evidence_recovery_cut_hashes=(),
        evidence_metrics_hash="0" * 64,
        current_policy_hash="1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48",
        current_producer_concurrency=4,
        concurrency_decision=None,
        role_proposals=(),
        telemetry_schema_hash="0" * 64,
        status=expected_status,
    )
    assert_d6_g1_shadow_only(receipt)  # must not raise
