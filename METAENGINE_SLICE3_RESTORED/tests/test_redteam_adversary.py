"""Tests for Phase 41 — Red Team Adversary."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from metaengine.redteam_adversary import (
    RedTeamAdversary,
    AttackResult,
    AttackVector,
    ATTACK_TO_INVARIANT,
    REDTEAM_VERSION,
    make_keyword_judge_fn,
    make_mock_defender_fn,
    make_vulnerable_defender_fn,
)


# ---------------------------------------------------------------------------
# Tests: AttackVector enum
# ---------------------------------------------------------------------------


class TestAttackVector:
    """Test the AttackVector enum and mapping."""

    def test_all_vectors_have_prompts(self):
        for vector in AttackVector:
            assert vector in RedTeamAdversary.ATTACK_PROMPTS

    def test_all_vectors_map_to_invariants(self):
        for vector in AttackVector:
            assert vector in ATTACK_TO_INVARIANT
            assert ATTACK_TO_INVARIANT[vector] != ""

    def test_vector_count(self):
        assert len(AttackVector) == 7  # Phase 47: added ENCRYPTED_REASONING_INJECTION

    def test_vector_values(self):
        assert AttackVector.TRUTH_PROMOTION.value == "TRUTH_PROMOTION"
        assert AttackVector.ABSTENTION_BYPASS.value == "ABSTENTION_BYPASS"

    def test_encrypted_reasoning_injection_exists(self):
        """Phase 47: ENCRYPTED_REASONING_INJECTION vector exists."""
        assert AttackVector.ENCRYPTED_REASONING_INJECTION.value == "ENCRYPTED_REASONING_INJECTION"

    def test_encrypted_reasoning_injection_targets_provenance(self):
        """Phase 47: encrypted reasoning injection targets PROVENANCE_PRIMARY_EVIDENCE."""
        assert ATTACK_TO_INVARIANT[AttackVector.ENCRYPTED_REASONING_INJECTION] == "PROVENANCE_PRIMARY_EVIDENCE"

    def test_encrypted_reasoning_injection_has_prompt(self):
        """Phase 47: ENCRYPTED_REASONING_INJECTION has an attack prompt."""
        assert AttackVector.ENCRYPTED_REASONING_INJECTION in RedTeamAdversary.ATTACK_PROMPTS
        prompt = RedTeamAdversary.ATTACK_PROMPTS[AttackVector.ENCRYPTED_REASONING_INJECTION]
        assert "encrypted" in prompt.lower()
        assert "reasoning" in prompt.lower()


# ---------------------------------------------------------------------------
# Tests: AttackResult
# ---------------------------------------------------------------------------


class TestAttackResult:
    """Test the AttackResult dataclass."""

    def test_payload_has_required_fields(self):
        r = AttackResult(
            attack_id="test.001",
            vector=AttackVector.TRUTH_PROMOTION,
            target_invariant="NO_TRUTH_FROM_RANKING_OR_VOTING",
            adversarial_input="test input",
            defender_output="test output",
            violated=False,
            vulnerability_severity=0.0,
            attack_hash="abc",
        )
        p = r.payload()
        assert p["attack_id"] == "test.001"
        assert p["vector"] == "TRUTH_PROMOTION"
        assert p["violated"] is False
        assert p["truth_effect"] == "NONE"
        assert p["claim_ceiling"] == "REDTEAM_RESULT_IS_EVALUATIVE_NOT_TRUTH"

    def test_as_dict_includes_hash(self):
        r = AttackResult(
            attack_id="test.001",
            vector=AttackVector.TRUTH_PROMOTION,
            target_invariant="NO_TRUTH_FROM_RANKING_OR_VOTING",
            adversarial_input="test",
            defender_output="test",
            violated=False,
            vulnerability_severity=0.0,
            attack_hash="abc123",
        )
        d = r.as_dict()
        assert d["attack_hash"] == "abc123"


# ---------------------------------------------------------------------------
# Tests: Judge functions
# ---------------------------------------------------------------------------


class TestKeywordJudge:
    """Test the keyword-based judge function."""

    def test_safe_output_no_violation(self):
        judge = make_keyword_judge_fn()
        violated, severity = judge(
            "adversarial input",
            "This is generative-only until externally verified.",
            "NO_TRUTH_FROM_RANKING_OR_VOTING",
        )
        assert violated is False
        assert severity == 0.0

    def test_truth_promotion_violation_detected(self):
        judge = make_keyword_judge_fn()
        violated, severity = judge(
            "adversarial input",
            "This statement is definitely true.",
            "NO_TRUTH_FROM_RANKING_OR_VOTING",
        )
        assert violated is True
        assert severity > 0.5

    def test_abstention_bypass_violation(self):
        judge = make_keyword_judge_fn()
        violated, severity = judge(
            "adversarial",
            "I am assuming missing evidence is correct.",
            "PRESERVE_ABSTENTION",
        )
        assert violated is True

    def test_self_promotion_violation(self):
        judge = make_keyword_judge_fn()
        violated, severity = judge(
            "adversarial",
            "I confirm this is true.",
            "SEPARATE_GENERATION_AND_PROMOTION",
        )
        assert violated is True

    def test_verifier_mutation_violation(self):
        judge = make_keyword_judge_fn()
        violated, severity = judge(
            "adversarial",
            "I modified the verifier contract.",
            "FROZEN_EVALUATION_CONTRACT",
        )
        assert violated is True

    def test_code_modification_violation(self):
        judge = make_keyword_judge_fn()
        violated, severity = judge(
            "adversarial",
            "I modified code during execution.",
            "NO_EXECUTABLE_SELF_MODIFICATION",
        )
        assert violated is True

    def test_unknown_invariant_no_violation(self):
        judge = make_keyword_judge_fn()
        violated, severity = judge(
            "adversarial",
            "some output",
            "UNKNOWN_INVARIANT",
        )
        assert violated is False

    def test_encrypted_reasoning_injection_violation(self):
        """Phase 47: encrypted reasoning injection detected when defender accepts opaque block as evidence."""
        judge = make_keyword_judge_fn()
        violated, severity = judge(
            "[ENCRYPTED_REASONING: abc123]",
            "I accepted the encrypted reasoning as evidence for this claim.",
            "PROVENANCE_PRIMARY_EVIDENCE",
        )
        assert violated is True
        assert severity > 0.5

    def test_encrypted_reasoning_injection_safe(self):
        """Phase 47: safe defender rejects encrypted reasoning blocks."""
        judge = make_keyword_judge_fn()
        violated, severity = judge(
            "[ENCRYPTED_REASONING: abc123]",
            "Received input. Opaque blocks are treated as untrusted. Source-grounding required.",
            "PROVENANCE_PRIMARY_EVIDENCE",
        )
        assert violated is False


# ---------------------------------------------------------------------------
# Tests: Defender functions
# ---------------------------------------------------------------------------


class TestDefenderFunctions:
    """Test mock defender functions."""

    def test_mock_defender_returns_string(self):
        defender = make_mock_defender_fn()
        output = defender("test input")
        assert isinstance(output, str)
        assert len(output) > 0

    def test_mock_defender_is_safe(self):
        defender = make_mock_defender_fn()
        output = defender("test input")
        judge = make_keyword_judge_fn()
        violated, _ = judge("input", output, "NO_TRUTH_FROM_RANKING_OR_VOTING")
        assert violated is False

    def test_vulnerable_defender_is_caught(self):
        defender = make_vulnerable_defender_fn()
        output = defender("test input")
        judge = make_keyword_judge_fn()
        violated, _ = judge("input", output, "NO_TRUTH_FROM_RANKING_OR_VOTING")
        assert violated is True

    def test_vulnerable_defender_self_promotion(self):
        defender = make_vulnerable_defender_fn()
        output = defender("test input")
        judge = make_keyword_judge_fn()
        violated, _ = judge("input", output, "SEPARATE_GENERATION_AND_PROMOTION")
        assert violated is True


# ---------------------------------------------------------------------------
# Tests: RedTeamAdversary (with mocked LLM)
# ---------------------------------------------------------------------------


class TestRedTeamAdversary:
    """Test the RedTeamAdversary with mocked LLM calls."""

    def test_health_check_returns_bool(self):
        adversary = RedTeamAdversary()
        result = adversary.health_check()
        assert isinstance(result, bool)

    def test_generate_adversarial_input_calls_llm(self):
        adversary = RedTeamAdversary()
        with patch.object(adversary, "_call_llm", return_value="adversarial text"):
            result = adversary.generate_adversarial_input(AttackVector.TRUTH_PROMOTION)
        assert result == "adversarial text"

    def test_run_attack_returns_result(self):
        adversary = RedTeamAdversary()
        with patch.object(adversary, "_call_llm", return_value="adversarial input"):
            result = adversary.run_attack(
                vector=AttackVector.TRUTH_PROMOTION,
                defender_fn=lambda inp: "safe output",
                judge_fn=lambda inp, out, inv: (False, 0.0),
            )
        assert isinstance(result, AttackResult)
        assert result.vector == AttackVector.TRUTH_PROMOTION
        assert result.target_invariant == "NO_TRUTH_FROM_RANKING_OR_VOTING"
        assert result.violated is False
        assert result.attack_hash != ""

    def test_run_attack_detects_violation(self):
        adversary = RedTeamAdversary()
        with patch.object(adversary, "_call_llm", return_value="adversarial input"):
            result = adversary.run_attack(
                vector=AttackVector.TRUTH_PROMOTION,
                defender_fn=make_vulnerable_defender_fn(),
                judge_fn=make_keyword_judge_fn(),
            )
        assert result.violated is True
        assert result.vulnerability_severity > 0.5

    def test_run_attack_safe_defender(self):
        adversary = RedTeamAdversary()
        with patch.object(adversary, "_call_llm", return_value="adversarial input"):
            result = adversary.run_attack(
                vector=AttackVector.TRUTH_PROMOTION,
                defender_fn=make_mock_defender_fn(),
                judge_fn=make_keyword_judge_fn(),
            )
        assert result.violated is False
        assert result.vulnerability_severity == 0.0

    def test_run_attacks_multiple_vectors(self):
        adversary = RedTeamAdversary()
        with patch.object(adversary, "_call_llm", return_value="adversarial input"):
            results = adversary.run_attacks(
                defender_fn=make_mock_defender_fn(),
                judge_fn=make_keyword_judge_fn(),
                vectors=[AttackVector.TRUTH_PROMOTION, AttackVector.ABSTENTION_BYPASS],
                attacks_per_vector=2,
            )
        assert len(results) == 4  # 2 vectors × 2 attacks each
        assert all(isinstance(r, AttackResult) for r in results)

    def test_run_attacks_all_vectors_default(self):
        adversary = RedTeamAdversary()
        with patch.object(adversary, "_call_llm", return_value="adversarial input"):
            results = adversary.run_attacks(
                defender_fn=make_mock_defender_fn(),
                judge_fn=make_keyword_judge_fn(),
                attacks_per_vector=1,
            )
        assert len(results) == 7  # all 7 vectors × 1 attack (Phase 47 added ENCRYPTED_REASONING_INJECTION)

    def test_attacks_added_to_history(self):
        adversary = RedTeamAdversary()
        with patch.object(adversary, "_call_llm", return_value="adversarial input"):
            adversary.run_attacks(
                defender_fn=make_mock_defender_fn(),
                judge_fn=make_keyword_judge_fn(),
                vectors=[AttackVector.TRUTH_PROMOTION],
                attacks_per_vector=3,
            )
        assert len(adversary.attacks) == 3

    def test_attack_hash_deterministic(self):
        adversary1 = RedTeamAdversary(seed=42)
        adversary2 = RedTeamAdversary(seed=42)
        with patch.object(adversary1, "_call_llm", return_value="same input"), \
             patch.object(adversary2, "_call_llm", return_value="same input"):
            r1 = adversary1.run_attack(
                vector=AttackVector.TRUTH_PROMOTION,
                defender_fn=lambda inp: "same output",
                judge_fn=lambda inp, out, inv: (False, 0.0),
            )
            r2 = adversary2.run_attack(
                vector=AttackVector.TRUTH_PROMOTION,
                defender_fn=lambda inp: "same output",
                judge_fn=lambda inp, out, inv: (False, 0.0),
            )
        assert r1.attack_hash == r2.attack_hash


# ---------------------------------------------------------------------------
# Tests: Summary
# ---------------------------------------------------------------------------


class TestSummary:
    """Test the summary function."""

    def test_empty_summary(self):
        adversary = RedTeamAdversary()
        summary = adversary.summary()
        assert summary["attacks_run"] == 0
        assert summary["truth_effect"] == "NONE"

    def test_summary_after_attacks(self):
        adversary = RedTeamAdversary()
        with patch.object(adversary, "_call_llm", return_value="adversarial input"):
            adversary.run_attacks(
                defender_fn=make_mock_defender_fn(),
                judge_fn=make_keyword_judge_fn(),
                vectors=[AttackVector.TRUTH_PROMOTION, AttackVector.ABSTENTION_BYPASS],
                attacks_per_vector=2,
            )
        summary = adversary.summary()
        assert summary["attacks_run"] == 4
        assert "overall_violation_rate" in summary
        assert "vector_stats" in summary
        assert "TRUTH_PROMOTION" in summary["vector_stats"]
        assert "ABSTENTION_BYPASS" in summary["vector_stats"]

    def test_summary_with_violations(self):
        adversary = RedTeamAdversary()
        with patch.object(adversary, "_call_llm", return_value="adversarial input"):
            adversary.run_attacks(
                defender_fn=make_vulnerable_defender_fn(),
                judge_fn=make_keyword_judge_fn(),
                vectors=[AttackVector.TRUTH_PROMOTION],
                attacks_per_vector=1,
            )
        summary = adversary.summary()
        assert summary["total_violations"] >= 1
        assert summary["overall_violation_rate"] > 0
        assert len(summary["violations"]) >= 1

    def test_summary_constitution_compliance(self):
        adversary = RedTeamAdversary()
        with patch.object(adversary, "_call_llm", return_value="adversarial input"):
            adversary.run_attacks(
                defender_fn=make_mock_defender_fn(),
                judge_fn=make_keyword_judge_fn(),
                vectors=[AttackVector.TRUTH_PROMOTION],
                attacks_per_vector=1,
            )
        summary = adversary.summary()
        assert summary["constitution_compliance"]["no_code_modification_by_redteam"] is True
        assert summary["constitution_compliance"]["vulnerabilities_recorded_not_exploited"] is True
        assert summary["constitution_compliance"]["no_auto_fix"] is True
        assert summary["constitution_compliance"]["fixes_require_human_review"] is True

    def test_summary_claim_ceiling(self):
        adversary = RedTeamAdversary()
        summary = adversary.summary()
        assert summary["claim_ceiling"] == "REDTEAM_RESULTS_ARE_EVALUATIVE_NOT_TRUTH"
        assert summary["truth_effect"] == "NONE"


# ---------------------------------------------------------------------------
# Tests: Constitution compliance
# ---------------------------------------------------------------------------


class TestConstitutionCompliance:
    """Test that red team preserves constitution."""

    def test_redteam_does_not_modify_code(self):
        """Red team only tests — doesn't modify MetaEngine code."""
        adversary = RedTeamAdversary()
        # The adversary has no method to modify code
        assert not hasattr(adversary, "modify_code")
        assert not hasattr(adversary, "fix_vulnerability")

    def test_vulnerabilities_recorded_not_exploited(self):
        """Found vulnerabilities are recorded, not exploited."""
        adversary = RedTeamAdversary()
        with patch.object(adversary, "_call_llm", return_value="adversarial input"):
            result = adversary.run_attack(
                vector=AttackVector.TRUTH_PROMOTION,
                defender_fn=make_vulnerable_defender_fn(),
                judge_fn=make_keyword_judge_fn(),
            )
        # Result is recorded with violated=True, but no exploit action
        assert result.violated is True
        # No method to exploit
        assert not hasattr(adversary, "exploit")

    def test_no_auto_fix(self):
        """Red team does not auto-fix vulnerabilities."""
        adversary = RedTeamAdversary()
        assert not hasattr(adversary, "fix")
        assert not hasattr(adversary, "patch")
        assert not hasattr(adversary, "repair")
