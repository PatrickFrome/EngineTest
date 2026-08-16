"""Tests for Phase 53 — Synthesis→Policy Bridge."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.synthesis_bridge import (
    SynthesisPolicyBridge,
    BridgeResult,
    BRIDGE_VERSION,
)
from metaengine.architecture_policy import ArchitecturePolicy, initial_policy, DIALECTIC_OPERATORS
from metaengine.architecture_synthesis import SynthesizedArchitecture, SynthesisResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bridge():
    return SynthesisPolicyBridge(max_rounds=2, max_deep_engines=4, exploration_rate=0.15)


@pytest.fixture
def synthesized_arch():
    """A synthesized architecture with valid dialectic operators."""
    return SynthesizedArchitecture(
        synthesis_id="synth.test.001",
        combined_mechanisms=("SOURCE_READING", "EVIDENCE_DISCRIMINATOR", "RIVAL_FORK"),
        rationale="Combining source reading with evidence discrimination and rival fork for deeper analysis.",
        novelty_score=0.75,
        synthesis_hash="abc123",
    )


@pytest.fixture
def synthesized_arch_invalid():
    """A synthesized architecture with invalid mechanisms."""
    return SynthesizedArchitecture(
        synthesis_id="synth.test.002",
        combined_mechanisms=("INVALID_OP", "FAKE_MECHANISM", "SOURCE_READING"),
        rationale="Some invalid mechanisms mixed with valid ones.",
        novelty_score=0.3,
        synthesis_hash="def456",
    )


@pytest.fixture
def synthesis_result():
    """A SynthesisResult with multiple syntheses."""
    syntheses = (
        SynthesizedArchitecture(
            synthesis_id="synth.001",
            combined_mechanisms=("SOURCE_READING", "EVIDENCE_DISCRIMINATOR"),
            rationale="test 1",
            novelty_score=0.7,
            synthesis_hash="h1",
        ),
        SynthesizedArchitecture(
            synthesis_id="synth.002",
            combined_mechanisms=("RIVAL_FORK", "OPERATOR_MUTATION"),
            rationale="test 2",
            novelty_score=0.8,
            synthesis_hash="h2",
        ),
    )
    return SynthesisResult(
        syntheses=syntheses,
        source_mechanisms=("SOURCE_READING", "EVIDENCE_DISCRIMINATOR", "RIVAL_FORK", "OPERATOR_MUTATION"),
        result_hash="result_hash_001",
    )


# ---------------------------------------------------------------------------
# Tests: BridgeResult
# ---------------------------------------------------------------------------


class TestBridgeResult:
    def test_payload_has_required_fields(self):
        r = BridgeResult(
            synthesis_id="synth.001",
            policy_hash="abc123def456",
            topology_id="SYNTH_001",
            dialectic_operators=("SOURCE_READING",),
            combined_mechanisms=("SOURCE_READING",),
            novelty_score=0.7,
            bridge_hash="hash",
        )
        p = r.payload()
        assert p["bridge_version"] == BRIDGE_VERSION
        assert p["synthesis_id"] == "synth.001"
        assert p["truth_effect"] == "NONE"

    def test_as_dict_includes_hash(self):
        r = BridgeResult(
            synthesis_id="s", policy_hash="p", topology_id="t",
            dialectic_operators=(), combined_mechanisms=(),
            novelty_score=0.5, bridge_hash="abc123",
        )
        d = r.as_dict()
        assert d["bridge_hash"] == "abc123"


# ---------------------------------------------------------------------------
# Tests: Mechanism validation
# ---------------------------------------------------------------------------


class TestMechanismValidation:
    def test_valid_mechanisms_pass(self, bridge):
        ops = bridge._validate_mechanisms(["SOURCE_READING", "EVIDENCE_DISCRIMINATOR"])
        assert "SOURCE_READING" in ops
        assert "EVIDENCE_DISCRIMINATOR" in ops

    def test_invalid_mechanisms_filtered(self, bridge):
        ops = bridge._validate_mechanisms(["INVALID_OP", "SOURCE_READING", "FAKE"])
        assert "INVALID_OP" not in ops
        assert "FAKE" not in ops
        assert "SOURCE_READING" in ops

    def test_all_invalid_uses_default(self, bridge):
        ops = bridge._validate_mechanisms(["INVALID", "FAKE"])
        assert len(ops) >= 1  # default set
        assert "SOURCE_READING" in ops or "EVIDENCE_DISCRIMINATOR" in ops

    def test_duplicates_removed(self, bridge):
        ops = bridge._validate_mechanisms(["SOURCE_READING", "SOURCE_READING", "RIVAL_FORK"])
        assert len(ops) == 2  # no duplicates

    def test_empty_uses_default(self, bridge):
        ops = bridge._validate_mechanisms([])
        assert len(ops) >= 1


# ---------------------------------------------------------------------------
# Tests: Synthesis to policy conversion
# ---------------------------------------------------------------------------


class TestSynthesisToPolicy:
    def test_returns_policy_and_result(self, bridge, synthesized_arch):
        policy, result = bridge.synthesis_to_policy(synthesized_arch)
        assert isinstance(policy, ArchitecturePolicy)
        assert isinstance(result, BridgeResult)

    def test_policy_is_shadow(self, bridge, synthesized_arch):
        policy, _ = bridge.synthesis_to_policy(synthesized_arch)
        assert policy.status == "SHADOW"

    def test_policy_has_synthesized_topology(self, bridge, synthesized_arch):
        policy, _ = bridge.synthesis_to_policy(synthesized_arch)
        assert policy.topology_id.startswith("SYNTH_")

    def test_policy_has_combined_operators(self, bridge, synthesized_arch):
        policy, _ = bridge.synthesis_to_policy(synthesized_arch)
        assert "SOURCE_READING" in policy.dialectic_operators
        assert "EVIDENCE_DISCRIMINATOR" in policy.dialectic_operators
        assert "RIVAL_FORK" in policy.dialectic_operators

    def test_policy_generation_increments(self, bridge, synthesized_arch):
        base = initial_policy()
        policy, _ = bridge.synthesis_to_policy(synthesized_arch, base)
        assert policy.generation == base.generation + 1

    def test_policy_parent_hash_set(self, bridge, synthesized_arch):
        base = initial_policy()
        policy, _ = bridge.synthesis_to_policy(synthesized_arch, base)
        assert policy.parent_policy_hash == base.policy_hash

    def test_policy_mutation_receipt_has_synthesis_id(self, bridge, synthesized_arch):
        policy, _ = bridge.synthesis_to_policy(synthesized_arch)
        assert policy.mutation_receipt["synthesis_id"] == synthesized_arch.synthesis_id
        assert policy.mutation_receipt["origin"] == "SYNTHESIS_POLICY_BRIDGE"

    def test_invalid_mechanisms_filtered_in_policy(self, bridge, synthesized_arch_invalid):
        policy, _ = bridge.synthesis_to_policy(synthesized_arch_invalid)
        # Only SOURCE_READING is valid from the invalid arch
        assert "SOURCE_READING" in policy.dialectic_operators
        assert "INVALID_OP" not in policy.dialectic_operators

    def test_result_has_bridge_hash(self, bridge, synthesized_arch):
        _, result = bridge.synthesis_to_policy(synthesized_arch)
        assert result.bridge_hash != ""

    def test_result_deterministic(self, bridge, synthesized_arch):
        p1, r1 = bridge.synthesis_to_policy(synthesized_arch)
        p2, r2 = bridge.synthesis_to_policy(synthesized_arch)
        assert r1.bridge_hash == r2.bridge_hash
        assert p1.policy_hash == p2.policy_hash

    def test_policy_passes_validation(self, bridge, synthesized_arch):
        policy, _ = bridge.synthesis_to_policy(synthesized_arch)
        policy.validate()  # should not raise

    def test_uses_base_policy_waves(self, bridge, synthesized_arch):
        base = initial_policy()
        policy, _ = bridge.synthesis_to_policy(synthesized_arch, base)
        assert policy.waves == base.waves  # inherited

    def test_uses_default_hyperparameters(self, bridge, synthesized_arch):
        policy, _ = bridge.synthesis_to_policy(synthesized_arch)
        assert policy.max_rounds == bridge.default_max_rounds
        assert policy.max_deep_engines == bridge.default_max_deep_engines


# ---------------------------------------------------------------------------
# Tests: Batch conversion
# ---------------------------------------------------------------------------


class TestBatchConversion:
    def test_batch_returns_multiple_policies(self, bridge, synthesis_result):
        results = bridge.synthesis_batch_to_policies(synthesis_result)
        assert len(results) == 2  # 2 syntheses

    def test_batch_policies_are_shadow(self, bridge, synthesis_result):
        results = bridge.synthesis_batch_to_policies(synthesis_result)
        for policy, _ in results:
            assert policy.status == "SHADOW"

    def test_batch_policies_have_different_operators(self, bridge, synthesis_result):
        results = bridge.synthesis_batch_to_policies(synthesis_result)
        ops1 = set(results[0][0].dialectic_operators)
        ops2 = set(results[1][0].dialectic_operators)
        assert ops1 != ops2  # different syntheses → different operators

    def test_batch_results_have_hashes(self, bridge, synthesis_result):
        results = bridge.synthesis_batch_to_policies(synthesis_result)
        for _, result in results:
            assert result.bridge_hash != ""


# ---------------------------------------------------------------------------
# Tests: Summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_summary_fields(self, bridge):
        s = bridge.summary()
        assert s["bridge_version"] == BRIDGE_VERSION
        assert "default_max_rounds" in s
        assert s["truth_effect"] == "NONE"

    def test_summary_constitution_compliance(self, bridge):
        s = bridge.summary()
        assert s["constitution_compliance"]["synthesized_policies_are_shadow"] is True
        assert s["constitution_compliance"]["no_auto_promotion"] is True
        assert s["constitution_compliance"]["mechanisms_validated"] is True


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    def test_policy_always_shadow(self, bridge, synthesized_arch):
        """Synthesized policies are always SHADOW — never ACTIVE."""
        policy, _ = bridge.synthesis_to_policy(synthesized_arch)
        assert policy.status == "SHADOW"

    def test_no_auto_promotion(self, bridge):
        """Bridge has no methods to promote policy."""
        assert not hasattr(bridge, "promote")
        assert not hasattr(bridge, "activate")

    def test_no_code_modification(self, bridge):
        """Bridge has no methods to modify code."""
        assert not hasattr(bridge, "modify_code")
        assert not hasattr(bridge, "execute_code")

    def test_claim_ceiling_preserved(self, bridge, synthesized_arch):
        _, result = bridge.synthesis_to_policy(synthesized_arch)
        assert "HYPOTHESIS" in result.payload()["claim_ceiling"]
        assert result.payload()["truth_effect"] == "NONE"

    def test_guardrail_hash_preserved(self, bridge, synthesized_arch):
        """Synthesized policy inherits base policy's guardrail hash."""
        base = initial_policy()
        policy, _ = bridge.synthesis_to_policy(synthesized_arch, base)
        assert policy.guardrail_hash == base.guardrail_hash  # immutable
