"""METAENGINE Phase 6 — Assimilation Loop tests."""

from __future__ import annotations

import pytest

from metaengine.assimilation_loop import (
    BehavioralFingerprint,
    FingerprintKind,
    MechanismHypothesis,
    TransferExperiment,
    AssimilationDecision,
    AssimilationResult,
    run_assimilation_loop,
    ASSIMILATION_LOOP_VERSION,
)


@pytest.fixture
def fingerprint():
    return BehavioralFingerprint(
        system_id="external-model-X",
        fingerprint_kind=FingerprintKind.BEHAVIORAL,
        observations=(("task_quality", "0.85"), ("long_context", "superior"), ("uncertainty", "adaptive")),
    )


@pytest.fixture
def hypothesis(fingerprint):
    return MechanismHypothesis(
        hypothesis_id="H1",
        mechanism_description="adaptive_verification_loop",
        expected_effect="reduces critical errors on high-uncertainty tasks",
        falsification_test="remove verification loop → quality drops below baseline",
        source_system_id=fingerprint.system_id,
    )


@pytest.fixture
def transfer_transferred(hypothesis):
    return TransferExperiment(
        experiment_id="TE1",
        mechanism_hypothesis_hash=hypothesis.hypothesis_hash,
        source_resource_id="model-X",
        target_resource_id="model-Y",
        result="TRANSFERRED",
        evidence_hash="a" * 64,
    )


@pytest.fixture
def transfer_not_transferred(hypothesis):
    return TransferExperiment(
        experiment_id="TE2",
        mechanism_hypothesis_hash=hypothesis.hypothesis_hash,
        source_resource_id="model-X",
        target_resource_id="model-Z",
        result="NOT_TRANSFERRED",
        evidence_hash="b" * 64,
    )


# ---------------------------------------------------------------------------
# BehavioralFingerprint
# ---------------------------------------------------------------------------


def test_fingerprint_hash(fingerprint):
    assert len(fingerprint.fingerprint_hash) == 64


def test_fingerprint_roundtrip(fingerprint):
    from metaengine.assimilation_loop import BehavioralFingerprint
    restored = BehavioralFingerprint.from_dict(fingerprint.payload())
    assert restored.fingerprint_hash == fingerprint.fingerprint_hash


# ---------------------------------------------------------------------------
# MechanismHypothesis
# ---------------------------------------------------------------------------


def test_hypothesis_hash(hypothesis):
    assert len(hypothesis.hypothesis_hash) == 64


# ---------------------------------------------------------------------------
# Assimilation decisions
# ---------------------------------------------------------------------------


def test_all_transferred_TRANSFERABLE(fingerprint, hypothesis, transfer_transferred):
    result = run_assimilation_loop(fingerprint, [hypothesis], [transfer_transferred])
    assert result.decision == AssimilationDecision.TRANSFERABLE
    assert result.mechanism_candidate_id is not None


def test_all_not_transferred_REJECTED(fingerprint, hypothesis, transfer_not_transferred):
    result = run_assimilation_loop(fingerprint, [hypothesis], [transfer_not_transferred])
    assert result.decision == AssimilationDecision.REJECTED
    assert result.mechanism_candidate_id is None


def test_mixed_CONTEXTUAL(fingerprint, hypothesis, transfer_transferred, transfer_not_transferred):
    result = run_assimilation_loop(fingerprint, [hypothesis], [transfer_transferred, transfer_not_transferred])
    assert result.decision == AssimilationDecision.CONTEXTUAL


def test_no_experiments_REJECTED(fingerprint, hypothesis):
    result = run_assimilation_loop(fingerprint, [hypothesis], [])
    assert result.decision == AssimilationDecision.REJECTED


# ---------------------------------------------------------------------------
# truth_effect + assimilation_effect always NONE
# ---------------------------------------------------------------------------


def test_truth_and_assimilation_none(fingerprint, hypothesis, transfer_transferred):
    result = run_assimilation_loop(fingerprint, [hypothesis], [transfer_transferred])
    assert result.truth_effect == "NONE"
    assert result.assimilation_effect == "NONE"  # stays NONE until separate gate


# ---------------------------------------------------------------------------
# Hash determinism + tamper
# ---------------------------------------------------------------------------


def test_result_hash_deterministic(fingerprint, hypothesis, transfer_transferred):
    r1 = run_assimilation_loop(fingerprint, [hypothesis], [transfer_transferred])
    r2 = run_assimilation_loop(fingerprint, [hypothesis], [transfer_transferred])
    assert r1.result_hash == r2.result_hash


def test_assimilation_effect_never_assimilated_automatically(fingerprint, hypothesis, transfer_transferred):
    """ASSIMILATED requires a separate authorized gate — never automatic."""
    result = run_assimilation_loop(fingerprint, [hypothesis], [transfer_transferred])
    assert result.decision != AssimilationDecision.ASSIMILATED
    assert result.assimilation_effect == "NONE"
