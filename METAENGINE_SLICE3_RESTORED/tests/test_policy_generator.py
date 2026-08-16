"""METAENGINE Phase 11 — Policy Generator + Tournament→Mechanism tests."""

from __future__ import annotations

import pytest

from metaengine.policy_generator import (
    GeneratedPolicyCandidate,
    generate_policy_from_mechanisms,
    extract_mechanism_from_tournament,
    POLICY_GENERATOR_VERSION,
)
from metaengine.mechanism_library import (
    MechanismCandidate,
    MechanismLibrary,
    MechanismState,
)
from metaengine.organization_policy import OrganizationType, OrganizationPolicyStatus


CONSTITUTION_HASH = "1b6311bd3dd6af060f05e63d22f3a28af776c117c4cc251c9383a6b8614f240d"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _a0_candidate(mid="mec.test_a0"):
    return MechanismCandidate.create(
        mechanism_id=mid, semantic_definition="d", origin_source_ids=("src",),
        source_fact_boundary="b", hypothesized_effect="e", resource_cost="low",
        complexity_cost="c", confidence="LOW", status=MechanismState.A0_OBSERVED,
    )


def _a2_candidate(mid="mec.test_a2"):
    """A2 candidate requires an A1 source + gate receipt — construct via AssimilationGate."""
    from metaengine.assimilation import AssimilationGate, ExperimentReceipt, AblationReceipt, TransferReceipt, TransferRegime
    from metaengine.util import sha256_bytes
    # Must start as A1, not A0
    cand = MechanismCandidate.create(
        mechanism_id=mid, semantic_definition="d", origin_source_ids=("src",),
        source_fact_boundary="b", hypothesized_effect="e", resource_cost="low",
        complexity_cost="c", confidence="LOW", status=MechanismState.A1_MECHANISM_HYPOTHESIS,
    )
    gate = AssimilationGate()
    exp = ExperimentReceipt.create(
        receipt_id="exp.1", mechanism_id=mid, implementation_ref="metaengine.test",
        regime="REASONING", result="REPRODUCED", evidence_sha256=sha256_bytes(b"exp"),
        verifier_ref="verifier", recorded_at="2026-08-14T00:00:00Z",
    )
    abl = AblationReceipt.create(
        receipt_id="abl.1", mechanism_id=mid, experiment_receipt_id="exp.1",
        ablated_component="test", result="EFFECT_DISAPPEARS",
        evidence_sha256=sha256_bytes(b"abl"), verifier_ref="verifier",
        recorded_at="2026-08-14T00:00:00Z",
    )
    trf = TransferReceipt.create(
        receipt_id="trf.1", mechanism_id=mid, source_regime=TransferRegime.GENERATION,
        target_regime=TransferRegime.REASONING, result="TRANSFERRED",
        evidence_sha256=sha256_bytes(b"trf"), verifier_ref="verifier",
        recorded_at="2026-08-14T00:00:00Z",
    )
    receipt = gate.advance_to_a2(candidate=cand, ablation=abl, transfer=trf, experiment=exp)
    return MechanismCandidate.create(
        mechanism_id=mid, semantic_definition="d", origin_source_ids=("src",),
        source_fact_boundary="b", hypothesized_effect="e", resource_cost="low",
        complexity_cost="c", confidence="MEDIUM", status=MechanismState.A2_TRANSFERABLE,
        promotion_authority=receipt,
    )


def _tournament_result(winner="P0", quality=0.9):
    return {
        "pareto_frontier": [
            {"policy_id": winner, "dominated": False, "metrics": {"quality": quality, "cost": 0.5, "latency": 0.3}},
            {"policy_id": "P1", "dominated": True, "metrics": {"quality": 0.5, "cost": 1.0, "latency": 0.8}},
        ],
        "mean_metrics": {winner: {"quality": quality, "cost": 0.5, "latency": 0.3}},
    }


# ---------------------------------------------------------------------------
# extract_mechanism_from_tournament
# ---------------------------------------------------------------------------


class TestExtractMechanismFromTournament:
    def test_extracts_winner(self):
        result = _tournament_result(winner="P0", quality=0.9)
        mech = extract_mechanism_from_tournament(result)
        assert mech is not None
        assert mech.status == MechanismState.A0_OBSERVED
        assert "P0" in mech.mechanism_id or "tournament" in mech.mechanism_id

    def test_no_winner_returns_none(self):
        result = {"pareto_frontier": [{"policy_id": "P0", "dominated": True, "metrics": {}}]}
        mech = extract_mechanism_from_tournament(result)
        assert mech is None

    def test_extracted_mechanism_has_tournament_origin(self):
        result = _tournament_result()
        mech = extract_mechanism_from_tournament(result)
        assert "tournament" in mech.origin_source_ids

    def test_extracted_mechanism_hash_deterministic(self):
        result = _tournament_result(winner="P0", quality=0.9)
        m1 = extract_mechanism_from_tournament(result)
        m2 = extract_mechanism_from_tournament(result)
        assert m1.mechanism_hash == m2.mechanism_hash

    def test_extracted_mechanism_is_a0(self):
        result = _tournament_result()
        mech = extract_mechanism_from_tournament(result)
        assert mech.status is MechanismState.A0_OBSERVED

    def test_extracted_mechanism_quality_in_hypothesis(self):
        result = _tournament_result(quality=0.85)
        mech = extract_mechanism_from_tournament(result)
        assert "0.85" in mech.hypothesized_effect or "quality" in mech.hypothesized_effect


# ---------------------------------------------------------------------------
# generate_policy_from_mechanisms
# ---------------------------------------------------------------------------


class TestGeneratePolicyFromMechanisms:
    def test_no_eligible_mechanisms_returns_none(self):
        lib = MechanismLibrary.create([_a0_candidate()])
        result = generate_policy_from_mechanisms(lib, constitution_hash=CONSTITUTION_HASH)
        assert result is None

    def test_a2_mechanism_generates_shadow_policy(self):
        a2 = _a2_candidate()
        lib = MechanismLibrary.create([a2])
        result = generate_policy_from_mechanisms(lib, constitution_hash=CONSTITUTION_HASH)
        assert result is not None
        assert result.shadow_status == OrganizationPolicyStatus.SHADOW
        assert result.truth_effect == "NONE"
        assert a2.mechanism_id in result.source_mechanism_ids

    def test_generated_candidate_hash_deterministic(self):
        a2 = _a2_candidate()
        lib = MechanismLibrary.create([a2])
        r1 = generate_policy_from_mechanisms(lib, constitution_hash=CONSTITUTION_HASH)
        r2 = generate_policy_from_mechanisms(lib, constitution_hash=CONSTITUTION_HASH)
        assert r1.candidate_hash == r2.candidate_hash

    def test_generated_policy_has_organization_type(self):
        a2 = _a2_candidate()
        lib = MechanismLibrary.create([a2])
        result = generate_policy_from_mechanisms(lib, constitution_hash=CONSTITUTION_HASH)
        assert result.organization_type in OrganizationType

    def test_generated_policy_rationale_mentions_mechanism(self):
        a2 = _a2_candidate(mid="mec.test_rationale")
        lib = MechanismLibrary.create([a2])
        result = generate_policy_from_mechanisms(lib, constitution_hash=CONSTITUTION_HASH)
        assert "mec.test_rationale" in result.generation_rationale

    def test_generated_policy_truth_effect_none(self):
        a2 = _a2_candidate()
        lib = MechanismLibrary.create([a2])
        result = generate_policy_from_mechanisms(lib, constitution_hash=CONSTITUTION_HASH)
        assert result.truth_effect == "NONE"

    def test_generated_policy_payload_serializable(self):
        a2 = _a2_candidate()
        lib = MechanismLibrary.create([a2])
        result = generate_policy_from_mechanisms(lib, constitution_hash=CONSTITUTION_HASH)
        d = result.payload()
        assert "generator_version" in d
        assert "policy_hash" in d
        assert "organization_type" in d

    def test_multiple_a2_mechanisms_in_source_ids(self):
        a2a = _a2_candidate(mid="mec.a")
        a2b = _a2_candidate(mid="mec.b")
        lib = MechanismLibrary.create([a2a, a2b])
        result = generate_policy_from_mechanisms(lib, constitution_hash=CONSTITUTION_HASH)
        assert len(result.source_mechanism_ids) == 2

    def test_a0_only_does_not_generate_policy(self):
        a0 = _a0_candidate()
        lib = MechanismLibrary.create([a0])
        result = generate_policy_from_mechanisms(lib, constitution_hash=CONSTITUTION_HASH)
        assert result is None

    def test_generator_version(self):
        assert POLICY_GENERATOR_VERSION == "METAENGINE-ORGANIZATION-POLICY-GENERATOR-1"


# ---------------------------------------------------------------------------
# Full pipeline: tournament → mechanism → library → policy
# ---------------------------------------------------------------------------


class TestFullPipeline:
    def test_tournament_to_policy_pipeline(self):
        """Full pipeline: tournament → extract mechanism → add to library → generate policy."""
        # Step 1: extract mechanism from tournament
        tournament = _tournament_result(winner="P_WINNER", quality=0.95)
        mech = extract_mechanism_from_tournament(tournament)
        assert mech is not None
        assert mech.status == MechanismState.A0_OBSERVED

        # Step 2: add to library
        lib = MechanismLibrary.create([])
        lib = lib.add_candidate(mech)
        assert len(lib.candidates) == 1

        # Step 3: A0 cannot generate policy (need A2+)
        result = generate_policy_from_mechanisms(lib, constitution_hash=CONSTITUTION_HASH)
        assert result is None  # A0 is not enough

        # Step 4: promote to A2 (simulated)
        a2 = _a2_candidate(mid=mech.mechanism_id)
        lib2 = MechanismLibrary.create([a2])
        result2 = generate_policy_from_mechanisms(lib2, constitution_hash=CONSTITUTION_HASH)
        assert result2 is not None
        assert result2.shadow_status == OrganizationPolicyStatus.SHADOW
        assert mech.mechanism_id in result2.source_mechanism_ids

    def test_mechanism_to_organization_type_mapping(self):
        """Different task_scopes map to different organization types."""
        from metaengine.policy_generator import _mechanism_to_organization_type
        for scope, expected_type in [
            (("ROUTING",), OrganizationType.SPECIALIST_ROUTING),
            (("MULTI_WAVE",), OrganizationType.SEQUENTIAL_PIPELINE),
            (("REASONING",), OrganizationType.RESOURCE_PLUS_VERIFIER),
            (("AGENTIC",), OrganizationType.HIERARCHICAL_FEDERATION),
            (("UNKNOWN",), OrganizationType.ONE_RESOURCE),
        ]:
            mech = MechanismCandidate.create(
                mechanism_id=f"mec.map.{scope[0].lower()}", semantic_definition="d",
                origin_source_ids=("src",), source_fact_boundary="b", hypothesized_effect="e",
                resource_cost="low", complexity_cost="c", confidence="LOW",
                status=MechanismState.A0_OBSERVED, task_scope=scope,
            )
            assert _mechanism_to_organization_type(mech) == expected_type
