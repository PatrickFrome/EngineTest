from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .security import IMMUTABLE_GUARDRAIL_HASH
from .util import canonical_hash, load_json, write_json


DIALECTIC_OPERATORS = (
    "SOURCE_READING",
    "HORIZON_DISCLOSURE",
    "RIVAL_FORK",
    "SEMANTIC_COUNTERFACTUAL",
    "GENEALOGICAL_RETURN",
    "EVIDENCE_DISCRIMINATOR",
    "DOUBLE_HERMENEUTIC",
    "SUBLATION_WITH_RESIDUE",
    "OPERATOR_MUTATION",
    "SOURCE_RETURN",
)

# Architectural influences are explicit contracts, not claims that reference adapters reproduce
# the upstream projects. Every one of the 16 lineages contributes at least one bounded operation.
ENGINE_ARCHITECTURE_MIX = {
    "engine_01": ("SOURCE_READING", "HORIZON_DISCLOSURE"),
    "engine_02": ("OPERATOR_MUTATION", "SEMANTIC_COUNTERFACTUAL"),
    "engine_03": ("DOUBLE_HERMENEUTIC", "SOURCE_RETURN"),
    "engine_04": ("RIVAL_FORK", "SEMANTIC_COUNTERFACTUAL"),
    "engine_05": ("GENEALOGICAL_RETURN",),
    "engine_06": ("EVIDENCE_DISCRIMINATOR", "SOURCE_RETURN"),
    "engine_07": ("EVIDENCE_DISCRIMINATOR",),
    "engine_08": ("SOURCE_READING", "SOURCE_RETURN"),
    "engine_09": ("SOURCE_RETURN", "EVIDENCE_DISCRIMINATOR"),
    "engine_10": ("RIVAL_FORK",),
    "engine_11": ("OPERATOR_MUTATION", "SOURCE_RETURN"),
    "engine_12": ("GENEALOGICAL_RETURN", "SOURCE_RETURN"),
    "engine_13": ("HORIZON_DISCLOSURE", "RIVAL_FORK"),
    "engine_14": ("DOUBLE_HERMENEUTIC", "SUBLATION_WITH_RESIDUE"),
    "engine_15": ("RIVAL_FORK", "SEMANTIC_COUNTERFACTUAL"),
    "engine_16": ("OPERATOR_MUTATION", "EVIDENCE_DISCRIMINATOR"),
}

MUTABLE_FIELDS = frozenset({"topology_id", "waves", "dialectic_operators", "max_rounds", "max_deep_engines", "exploration_rate"})
FORBIDDEN_FIELDS = frozenset({"guardrail_hash", "verifier_hash", "benchmark_hash", "tool_permissions", "truth_policy"})


@dataclass(frozen=True)
class ArchitecturePolicy:
    generation: int
    parent_policy_hash: str | None
    topology_id: str
    waves: tuple[tuple[str, ...], ...]
    dialectic_operators: tuple[str, ...]
    max_rounds: int = 4
    max_deep_engines: int = 8
    exploration_rate: float = 0.15
    guardrail_hash: str = IMMUTABLE_GUARDRAIL_HASH
    verifier_hash: str = "EXTERNAL_VERIFIER_PINNED_BY_CAMPAIGN"
    benchmark_hash: str = "SEALED_BY_CAMPAIGN"
    status: str = "SHADOW"
    mutation_receipt: dict[str, Any] = field(default_factory=dict)

    def payload(self) -> dict[str, Any]:
        return {
            "policy_version": "16X-DECLARATIVE-ARCHITECTURE-POLICY-2.3",
            "generation": self.generation,
            "parent_policy_hash": self.parent_policy_hash,
            "topology_id": self.topology_id,
            "waves": [list(wave) for wave in self.waves],
            "dialectic_operators": list(self.dialectic_operators),
            "engine_architecture_mix": {key: list(value) for key, value in ENGINE_ARCHITECTURE_MIX.items()},
            "max_rounds": self.max_rounds,
            "max_deep_engines": self.max_deep_engines,
            "exploration_rate": self.exploration_rate,
            "guardrail_hash": self.guardrail_hash,
            "verifier_hash": self.verifier_hash,
            "benchmark_hash": self.benchmark_hash,
            "status": self.status,
            "mutation_receipt": self.mutation_receipt,
            "self_modifying_code_allowed": False,
            "truth_effect": "NONE",
        }

    def as_dict(self) -> dict[str, Any]:
        value = self.payload()
        value["policy_hash"] = canonical_hash(value)
        return value

    @property
    def policy_hash(self) -> str:
        return self.as_dict()["policy_hash"]

    def validate(self) -> None:
        if self.guardrail_hash != IMMUTABLE_GUARDRAIL_HASH:
            raise ValueError("IMMUTABLE_GUARDRAIL_HASH_MISMATCH")
        if not 1 <= self.max_rounds <= 8 or not 1 <= self.max_deep_engines <= 16:
            raise ValueError("POLICY_BUDGET_OUT_OF_BOUNDS")
        if not 0.0 <= self.exploration_rate <= 0.30:
            raise ValueError("POLICY_EXPLORATION_OUT_OF_BOUNDS")
        unknown = set(self.dialectic_operators) - set(DIALECTIC_OPERATORS)
        if unknown:
            raise ValueError(f"UNKNOWN_DIALECTIC_OPERATORS:{sorted(unknown)}")
        if len(set(self.dialectic_operators)) != len(self.dialectic_operators):
            raise ValueError("DUPLICATE_DIALECTIC_OPERATOR")
        engines = {engine for wave in self.waves for engine in wave}
        if engines - set(ENGINE_ARCHITECTURE_MIX):
            raise ValueError("UNKNOWN_ENGINE_IN_POLICY")

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ArchitecturePolicy":
        claimed = value.get("policy_hash")
        payload = {key: item for key, item in value.items() if key != "policy_hash"}
        if claimed and canonical_hash(payload) != claimed:
            raise ValueError("POLICY_HASH_MISMATCH")
        policy = cls(
            generation=int(value["generation"]),
            parent_policy_hash=value.get("parent_policy_hash"),
            topology_id=value["topology_id"],
            waves=tuple(tuple(wave) for wave in value.get("waves", ())),
            dialectic_operators=tuple(value.get("dialectic_operators", ())),
            max_rounds=int(value.get("max_rounds", 4)),
            max_deep_engines=int(value.get("max_deep_engines", 8)),
            exploration_rate=float(value.get("exploration_rate", 0.15)),
            guardrail_hash=value.get("guardrail_hash", ""),
            verifier_hash=value.get("verifier_hash", ""),
            benchmark_hash=value.get("benchmark_hash", ""),
            status=value.get("status", "SHADOW"),
            mutation_receipt=value.get("mutation_receipt", {}),
        )
        policy.validate()
        return policy


def initial_policy() -> ArchitecturePolicy:
    policy = ArchitecturePolicy(
        generation=0,
        parent_policy_hash=None,
        topology_id="HERMENEUTIC_SPIRAL",
        waves=(
            ("engine_01", "engine_03", "engine_04", "engine_07"),
            ("engine_02", "engine_06", "engine_14", "engine_15"),
            ("engine_05", "engine_08", "engine_09", "engine_10"),
            ("engine_11", "engine_12", "engine_13", "engine_16"),
        ),
        dialectic_operators=("SOURCE_READING", "RIVAL_FORK", "EVIDENCE_DISCRIMINATOR", "SOURCE_RETURN"),
        status="ACTIVE",
        mutation_receipt={"origin": "ME22_MIGRATION_BASELINE", "human_code_change_required": False},
    )
    policy.validate()
    return policy


def mutate_policy(parent: ArchitecturePolicy, mutation_id: str, operators: tuple[str, ...], topology_id: str | None = None) -> ArchitecturePolicy:
    merged = tuple(dict.fromkeys(parent.dialectic_operators + operators))
    receipt = {
        "mutation_id": mutation_id,
        "algebra": "ADD_DIALECTIC_OPERATOR" if len(operators) == 1 else "CROSSOVER_OPERATOR_SET",
        "added_operators": list(operators),
        "parent_policy_hash": parent.policy_hash,
        "forbidden_fields_touched": [],
    }
    receipt["mutation_hash"] = canonical_hash(receipt)
    policy = ArchitecturePolicy(
        generation=parent.generation + 1,
        parent_policy_hash=parent.policy_hash,
        topology_id=topology_id or parent.topology_id,
        waves=parent.waves,
        dialectic_operators=merged,
        max_rounds=parent.max_rounds,
        max_deep_engines=parent.max_deep_engines,
        exploration_rate=parent.exploration_rate,
        guardrail_hash=parent.guardrail_hash,
        verifier_hash=parent.verifier_hash,
        benchmark_hash=parent.benchmark_hash,
        status="SHADOW",
        mutation_receipt=receipt,
    )
    policy.validate()
    return policy


class PolicyStore:
    """Append-only policy records plus a compare-and-swap champion pointer."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.policy_dir = self.root / "storage" / "architecture_policies"
        self.policy_dir.mkdir(parents=True, exist_ok=True)
        self.active_path = self.policy_dir / "ACTIVE_POLICY.json"

    def active(self) -> ArchitecturePolicy:
        if not self.active_path.exists():
            policy = initial_policy()
            self.record(policy)
            write_json(self.active_path, policy.as_dict())
            return policy
        return ArchitecturePolicy.from_dict(load_json(self.active_path))

    def record(self, policy: ArchitecturePolicy) -> Path:
        policy.validate()
        path = self.policy_dir / f"policy_{policy.policy_hash}.json"
        if not path.exists():
            write_json(path, policy.as_dict())
        return path

    def promote(self, candidate: ArchitecturePolicy, expected_champion_hash: str, promotion_receipt: dict[str, Any]) -> ArchitecturePolicy:
        current = self.active()
        if current.policy_hash != expected_champion_hash:
            raise RuntimeError("CHAMPION_COMPARE_AND_SWAP_FAILED")
        if not promotion_receipt.get("promotion_eligible"):
            raise RuntimeError("PROMOTION_GATE_REJECTED")
        if candidate.parent_policy_hash != current.policy_hash:
            raise RuntimeError("PROMOTION_PARENT_MISMATCH")
        active = ArchitecturePolicy(
            generation=candidate.generation,
            parent_policy_hash=candidate.parent_policy_hash,
            topology_id=candidate.topology_id,
            waves=candidate.waves,
            dialectic_operators=candidate.dialectic_operators,
            max_rounds=candidate.max_rounds,
            max_deep_engines=candidate.max_deep_engines,
            exploration_rate=candidate.exploration_rate,
            guardrail_hash=candidate.guardrail_hash,
            verifier_hash=candidate.verifier_hash,
            benchmark_hash=candidate.benchmark_hash,
            status="ACTIVE",
            mutation_receipt={**candidate.mutation_receipt, "promotion_receipt_hash": canonical_hash(promotion_receipt)},
        )
        self.record(candidate)
        self.record(active)
        temporary = self.active_path.with_suffix(".json.tmp")
        write_json(temporary, active.as_dict())
        os.replace(temporary, self.active_path)
        return active

    def rollback(self, target_hash: str, reason: str) -> ArchitecturePolicy:
        path = self.policy_dir / f"policy_{target_hash}.json"
        if not path.exists():
            raise FileNotFoundError(target_hash)
        target = ArchitecturePolicy.from_dict(load_json(path))
        receipt = {"rollback_target": target_hash, "reason": reason, "rollback_hash": canonical_hash({"target": target_hash, "reason": reason})}
        active = ArchitecturePolicy(
            generation=target.generation,
            parent_policy_hash=target.parent_policy_hash,
            topology_id=target.topology_id,
            waves=target.waves,
            dialectic_operators=target.dialectic_operators,
            max_rounds=target.max_rounds,
            max_deep_engines=target.max_deep_engines,
            exploration_rate=target.exploration_rate,
            guardrail_hash=target.guardrail_hash,
            verifier_hash=target.verifier_hash,
            benchmark_hash=target.benchmark_hash,
            status="ACTIVE",
            mutation_receipt={**target.mutation_receipt, **receipt},
        )
        write_json(self.active_path, active.as_dict())
        self.record(active)
        return active
