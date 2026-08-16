"""METAENGINE — D6-G1 shadow-only invariant tests (Boundary code enforcement).

D6-G1 is PASS_ADAPTATION_SHADOW_READY: adaptation evidence may be produced and
shadow proposals readied, but NO canonical activation occurs. This test
enforces the ``assert_d6_g1_shadow_only`` guard.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from metaengine.devfabric.federation.adaptation import (
    AdaptationReceipt,
    D6_G1_FORBIDDEN_CANONICAL_STATUSES,
    D6_G1_SHADOW_ONLY_STATUSES,
    assert_d6_g1_shadow_only,
)


def _shadow_receipt(status: str = "SHADOW_PROPOSAL_READY") -> AdaptationReceipt:
    """Build a minimal AdaptationReceipt with the given status."""
    return AdaptationReceipt(
        protocol_version="D6.ADAPTATION.1",
        adaptation_input_hash="0" * 64,
        adaptation_receipt_hash="0" * 64,
        evidence_finalization_hashes=(),
        evidence_recovery_cut_hashes=(),
        evidence_metrics_hash="0" * 64,
        current_policy_hash="1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48",
        current_producer_concurrency=4,
        concurrency_decision=None,  # type: ignore[arg-type]
        role_proposals=(),
        telemetry_schema_hash="0" * 64,
        status=status,
    )


def test_shadow_only_statuses_do_not_include_canonical():
    """The allowed shadow-only statuses must NOT include any canonical-activation status."""
    assert D6_G1_SHADOW_ONLY_STATUSES.isdisjoint(D6_G1_FORBIDDEN_CANONICAL_STATUSES)


def test_shadow_proposal_ready_passes_guard():
    r = _shadow_receipt("SHADOW_PROPOSAL_READY")
    assert_d6_g1_shadow_only(r)  # must not raise


def test_hold_unobserved_metric_passes_guard():
    r = _shadow_receipt("HOLD_UNOBSERVED_METRIC")
    assert_d6_g1_shadow_only(r)


def test_hold_insufficient_evidence_passes_guard():
    r = _shadow_receipt("HOLD_INSUFFICIENT_EVIDENCE")
    assert_d6_g1_shadow_only(r)


@pytest.mark.parametrize("forbidden", sorted(D6_G1_FORBIDDEN_CANONICAL_STATUSES))
def test_canonical_activation_status_rejected(forbidden: str):
    """Any canonical-activation status must be rejected by the guard."""
    r = _shadow_receipt(forbidden)
    with pytest.raises(ValueError, match="D6_G1_SHADOW_ONLY_VIOLATION"):
        assert_d6_g1_shadow_only(r)


def test_unknown_status_rejected():
    """An unrecognized status must be rejected (defensive)."""
    r = _shadow_receipt("SOME_BOGUS_STATUS")
    with pytest.raises(ValueError, match="D6_G1_UNKNOWN_ADAPTATION_STATUS"):
        assert_d6_g1_shadow_only(r)


def test_guard_catches_tampered_receipt():
    """If a shadow receipt is tampered to ACTIVE, the guard catches it."""
    r = _shadow_receipt("SHADOW_PROPOSAL_READY")
    assert_d6_g1_shadow_only(r)  # original passes
    tampered = replace(r, status="ACTIVE")
    with pytest.raises(ValueError, match="D6_G1_SHADOW_ONLY_VIOLATION"):
        assert_d6_g1_shadow_only(tampered)
