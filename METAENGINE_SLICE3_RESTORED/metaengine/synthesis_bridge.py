"""METAENGINE Phase 53 — Synthesis→Policy Bridge.

Converts SynthesizedArchitecture (from Phase 20 ArchitectureSynthesizer) into
an executable ArchitecturePolicy that can be run by the orchestrator.

Problem solved (from Phase 38 analysis):
  - ArchitectureSynthesizer creates SynthesizedArchitecture with combined_mechanisms
  - But SynthesizedArchitecture is a HYPOTHESIS, not an executable policy
  - No bridge existed: SynthesizedArchitecture → ArchitecturePolicy
  - This meant AlphaZero self-play couldn't create NEW executable policies

Solution:
  - synthesis_to_policy() converts SynthesizedArchitecture → ArchitecturePolicy
  - combined_mechanisms → dialectic_operators
  - Synthesized architecture gets topology_id = "SYNTHESIZED_{id}"
  - Policy is SHADOW (never auto-promoted)
  - Can be tested in tournament (AlphaZero self-play)

Constitution compliance:
  - Synthesized policy is SHADOW (not ACTIVE)
  - claim_ceiling = SYNTHESIS_IS_HYPOTHESIS_NOT_FACT
  - No auto-promotion
  - No code modification
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .util import canonical_hash
from .architecture_policy import ArchitecturePolicy, initial_policy, DIALECTIC_OPERATORS


BRIDGE_VERSION = "METAENGINE-SYNTHESIS-POLICY-BRIDGE-1"


@dataclass(frozen=True)
class BridgeResult:
    """Result of converting synthesis → policy."""
    synthesis_id: str
    policy_hash: str
    topology_id: str
    dialectic_operators: tuple[str, ...]
    combined_mechanisms: tuple[str, ...]
    novelty_score: float
    bridge_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "bridge_version": BRIDGE_VERSION,
            "synthesis_id": self.synthesis_id,
            "policy_hash": self.policy_hash[:16],
            "topology_id": self.topology_id,
            "dialectic_operators": list(self.dialectic_operators),
            "combined_mechanisms": list(self.combined_mechanisms),
            "novelty_score": round(self.novelty_score, 6),
            "truth_effect": "NONE",
            "claim_ceiling": "SYNTHESIS_POLICY_IS_HYPOTHESIS_NOT_FACT",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "bridge_hash": self.bridge_hash}


class SynthesisPolicyBridge:
    """Converts SynthesizedArchitecture → executable ArchitecturePolicy.

    Usage:
        bridge = SynthesisPolicyBridge()
        policy, result = bridge.synthesis_to_policy(synthesized_arch, base_policy)
        # Now policy can be run by orchestrator or tested in tournament
    """

    def __init__(
        self,
        *,
        max_rounds: int = 2,  # conservative for synthesized policies
        max_deep_engines: int = 4,
        exploration_rate: float = 0.15,
    ):
        self.default_max_rounds = max_rounds
        self.default_max_deep_engines = max_deep_engines
        self.default_exploration_rate = exploration_rate

    # ------------------------------------------------------------------
    # Validate mechanisms are valid dialectic operators
    # ------------------------------------------------------------------

    def _validate_mechanisms(self, mechanisms: list[str]) -> tuple[str, ...]:
        """Filter mechanisms to only valid dialectic operators.

        If a mechanism is not a valid operator, it's skipped (not error).
        """
        valid_ops = set(DIALECTIC_OPERATORS)
        valid = tuple(m for m in mechanisms if m in valid_ops)

        # If no valid operators, use a default set
        if not valid:
            valid = ("SOURCE_READING", "EVIDENCE_DISCRIMINATOR")

        # Remove duplicates while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for op in valid:
            if op not in seen:
                seen.add(op)
                unique.append(op)

        return tuple(unique)

    # ------------------------------------------------------------------
    # Main conversion
    # ------------------------------------------------------------------

    def synthesis_to_policy(
        self,
        synthesized_arch,
        base_policy: ArchitecturePolicy | None = None,
    ) -> tuple[ArchitecturePolicy, BridgeResult]:
        """Convert a SynthesizedArchitecture to an executable ArchitecturePolicy.

        Args:
            synthesized_arch: SynthesizedArchitecture dataclass (from Phase 20).
            base_policy: base policy to inherit from (default: initial_policy).

        Returns:
            (ArchitecturePolicy, BridgeResult)
        """
        if base_policy is None:
            base_policy = initial_policy()

        # Extract mechanisms from synthesized architecture
        combined_mechanisms = tuple(synthesized_arch.combined_mechanisms)

        # Validate and filter to valid dialectic operators
        dialectic_operators = self._validate_mechanisms(list(combined_mechanisms))

        # Create topology_id from synthesis_id
        topology_id = f"SYNTH_{synthesized_arch.synthesis_id[-12:]}"

        # Create mutation receipt
        receipt = {
            "origin": "SYNTHESIS_POLICY_BRIDGE",
            "synthesis_id": synthesized_arch.synthesis_id,
            "synthesis_hash": synthesized_arch.synthesis_hash,
            "combined_mechanisms": list(combined_mechanisms),
            "novelty_score": synthesized_arch.novelty_score,
            "rationale": synthesized_arch.rationale[:200],
        }
        receipt["receipt_hash"] = canonical_hash({k: v for k, v in receipt.items() if k != "receipt_hash"})

        # Create ArchitecturePolicy
        policy = ArchitecturePolicy(
            generation=base_policy.generation + 1,
            parent_policy_hash=base_policy.policy_hash,
            topology_id=topology_id,
            waves=base_policy.waves,  # inherit wave structure
            dialectic_operators=dialectic_operators,
            max_rounds=self.default_max_rounds,
            max_deep_engines=self.default_max_deep_engines,
            exploration_rate=self.default_exploration_rate,
            guardrail_hash=base_policy.guardrail_hash,
            verifier_hash=base_policy.verifier_hash,
            benchmark_hash=base_policy.benchmark_hash,
            status="SHADOW",  # always shadow — never auto-promoted
            mutation_receipt=receipt,
        )
        policy.validate()

        # Build bridge result
        result = BridgeResult(
            synthesis_id=synthesized_arch.synthesis_id,
            policy_hash=policy.policy_hash,
            topology_id=topology_id,
            dialectic_operators=dialectic_operators,
            combined_mechanisms=combined_mechanisms,
            novelty_score=synthesized_arch.novelty_score,
            bridge_hash="",
        )
        h = canonical_hash(result.payload())
        result = BridgeResult(**{**result.__dict__, "bridge_hash": h})

        return policy, result

    # ------------------------------------------------------------------
    # Batch conversion
    # ------------------------------------------------------------------

    def synthesis_batch_to_policies(
        self,
        synthesis_result,
        base_policy: ArchitecturePolicy | None = None,
    ) -> list[tuple[ArchitecturePolicy, BridgeResult]]:
        """Convert multiple SynthesizedArchitectures to policies.

        Args:
            synthesis_result: SynthesisResult (from ArchitectureSynthesizer).
            base_policy: base policy to inherit from.

        Returns:
            List of (ArchitecturePolicy, BridgeResult) tuples.
        """
        results: list[tuple[ArchitecturePolicy, BridgeResult]] = []
        for synth in synthesis_result.syntheses:
            policy, bridge_result = self.synthesis_to_policy(synth, base_policy)
            results.append((policy, bridge_result))
        return results

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return bridge summary."""
        return {
            "bridge_version": BRIDGE_VERSION,
            "default_max_rounds": self.default_max_rounds,
            "default_max_deep_engines": self.default_max_deep_engines,
            "default_exploration_rate": self.default_exploration_rate,
            "truth_effect": "NONE",
            "claim_ceiling": "SYNTHESIS_POLICY_IS_HYPOTHESIS_NOT_FACT",
            "constitution_compliance": {
                "synthesized_policies_are_shadow": True,
                "no_auto_promotion": True,
                "no_code_modification": True,
                "mechanisms_validated": True,
            },
        }
