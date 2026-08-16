"""METAENGINE — direct tests for architecture_policy.py (was 0 tests — critical gap).

Covers: forbidden fields immutability, guardrail hash, policy hash determinism,
mutation lineage, validation bounds, from_dict tamper detection.
"""

from __future__ import annotations

import pytest

from metaengine.architecture_policy import (
    ENGINE_ARCHITECTURE_MIX,
    FORBIDDEN_FIELDS,
    MUTABLE_FIELDS,
    ArchitecturePolicy,
    initial_policy,
    mutate_policy,
)
from metaengine.security import IMMUTABLE_GUARDRAIL_HASH
from metaengine.util import canonical_hash


# ---------------------------------------------------------------------------
# FORBIDDEN_FIELDS / MUTABLE_FIELDS invariant
# ---------------------------------------------------------------------------


def test_forbidden_fields_are_not_mutable():
    """FORBIDDEN_FIELDS and MUTABLE_FIELDS must be disjoint."""
    assert FORBIDDEN_FIELDS.isdisjoint(MUTABLE_FIELDS), (
        "a field is both FORBIDDEN and MUTABLE — policy invariant broken"
    )


def test_forbidden_fields_contains_guardrail_verifier_benchmark():
    """The integrity-critical hashes must be forbidden from mutation."""
    assert "guardrail_hash" in FORBIDDEN_FIELDS
    assert "verifier_hash" in FORBIDDEN_FIELDS
    assert "benchmark_hash" in FORBIDDEN_FIELDS
    assert "tool_permissions" in FORBIDDEN_FIELDS
    assert "truth_policy" in FORBIDDEN_FIELDS


def test_self_modifying_code_allowed_is_false_constant():
    """self_modifying_code_allowed is hardcoded False in payload (not a field)."""
    p = initial_policy()
    payload = p.payload()
    assert payload["self_modifying_code_allowed"] is False
    assert payload["truth_effect"] == "NONE"


# ---------------------------------------------------------------------------
# Guardrail immutability
# ---------------------------------------------------------------------------


def test_guardrail_hash_immutable():
    p = initial_policy()
    assert p.guardrail_hash == IMMUTABLE_GUARDRAIL_HASH


def test_policy_with_wrong_guardrail_rejected():
    p = initial_policy()
    with pytest.raises(ValueError, match="IMMUTABLE_GUARDRAIL_HASH_MISMATCH"):
        ArchitecturePolicy(
            generation=p.generation,
            parent_policy_hash=p.parent_policy_hash,
            topology_id=p.topology_id,
            waves=p.waves,
            dialectic_operators=p.dialectic_operators,
            guardrail_hash="WRONG_HASH",
        ).validate()


# ---------------------------------------------------------------------------
# Policy hash determinism + tamper detection
# ---------------------------------------------------------------------------


def test_policy_hash_deterministic():
    p1 = initial_policy()
    p2 = initial_policy()
    assert p1.policy_hash == p2.policy_hash
    assert len(p1.policy_hash) == 64


def test_policy_from_dict_revalidates_hash():
    p = initial_policy()
    restored = ArchitecturePolicy.from_dict(p.as_dict())
    assert restored.policy_hash == p.policy_hash


def test_policy_from_dict_rejects_tampered_hash():
    p = initial_policy()
    tampered = p.as_dict()
    tampered["policy_hash"] = "0" * 64
    with pytest.raises(ValueError, match="POLICY_HASH_MISMATCH"):
        ArchitecturePolicy.from_dict(tampered)


def test_policy_from_dict_rejects_tampered_payload():
    p = initial_policy()
    tampered = p.as_dict()
    tampered["generation"] = 999
    # policy_hash is the original (stale)
    with pytest.raises(ValueError, match="POLICY_HASH_MISMATCH"):
        ArchitecturePolicy.from_dict(tampered)


# ---------------------------------------------------------------------------
# Validation bounds
# ---------------------------------------------------------------------------


def test_max_rounds_out_of_bounds_rejected():
    p = initial_policy()
    with pytest.raises(ValueError, match="POLICY_BUDGET_OUT_OF_BOUNDS"):
        ArchitecturePolicy(
            generation=p.generation, parent_policy_hash=p.parent_policy_hash,
            topology_id=p.topology_id, waves=p.waves, dialectic_operators=p.dialectic_operators,
            max_rounds=0,
        ).validate()
    with pytest.raises(ValueError, match="POLICY_BUDGET_OUT_OF_BOUNDS"):
        ArchitecturePolicy(
            generation=p.generation, parent_policy_hash=p.parent_policy_hash,
            topology_id=p.topology_id, waves=p.waves, dialectic_operators=p.dialectic_operators,
            max_rounds=9,
        ).validate()


def test_exploration_rate_out_of_bounds_rejected():
    p = initial_policy()
    with pytest.raises(ValueError, match="POLICY_EXPLORATION_OUT_OF_BOUNDS"):
        ArchitecturePolicy(
            generation=p.generation, parent_policy_hash=p.parent_policy_hash,
            topology_id=p.topology_id, waves=p.waves, dialectic_operators=p.dialectic_operators,
            exploration_rate=0.5,
        ).validate()


def test_unknown_dialectic_operator_rejected():
    p = initial_policy()
    with pytest.raises(ValueError, match="UNKNOWN_DIALECTIC_OPERATORS"):
        ArchitecturePolicy(
            generation=p.generation, parent_policy_hash=p.parent_policy_hash,
            topology_id=p.topology_id, waves=p.waves,
            dialectic_operators=("SOURCE_READING", "BOGUS_OPERATOR"),
        ).validate()


def test_duplicate_dialectic_operator_rejected():
    p = initial_policy()
    with pytest.raises(ValueError, match="DUPLICATE_DIALECTIC_OPERATOR"):
        ArchitecturePolicy(
            generation=p.generation, parent_policy_hash=p.parent_policy_hash,
            topology_id=p.topology_id, waves=p.waves,
            dialectic_operators=("SOURCE_READING", "SOURCE_READING"),
        ).validate()


def test_unknown_engine_in_waves_rejected():
    p = initial_policy()
    with pytest.raises(ValueError, match="UNKNOWN_ENGINE_IN_POLICY"):
        ArchitecturePolicy(
            generation=p.generation, parent_policy_hash=p.parent_policy_hash,
            topology_id=p.topology_id,
            waves=(("engine_01", "engine_99"),),
            dialectic_operators=p.dialectic_operators,
        ).validate()


# ---------------------------------------------------------------------------
# Mutation lineage
# ---------------------------------------------------------------------------


def test_mutate_policy_creates_child_with_parent_hash():
    parent = initial_policy()
    child = mutate_policy(parent, mutation_id="m001", operators=("HORIZON_DISCLOSURE",))
    assert child.parent_policy_hash == parent.policy_hash
    assert child.generation == parent.generation + 1
    assert "HORIZON_DISCLOSURE" in child.dialectic_operators


def test_mutate_policy_preserves_forbidden_fields():
    """Mutation must NOT change guardrail/verifier/benchmark hashes."""
    parent = initial_policy()
    child = mutate_policy(parent, mutation_id="m002", operators=("GENEALOGICAL_RETURN",))
    assert child.guardrail_hash == parent.guardrail_hash
    assert child.verifier_hash == parent.verifier_hash
    assert child.benchmark_hash == parent.benchmark_hash


def test_mutate_policy_deduplicates_operators():
    parent = initial_policy()
    child = mutate_policy(parent, mutation_id="m003", operators=("SOURCE_READING",))
    # SOURCE_READING is already in parent; child should not duplicate it
    assert child.dialectic_operators.count("SOURCE_READING") == 1


def test_mutate_policy_records_mutation_receipt():
    parent = initial_policy()
    child = mutate_policy(parent, mutation_id="m004", operators=("SUBLATION_WITH_RESIDUE",))
    assert child.mutation_receipt["mutation_id"] == "m004"
    assert child.mutation_receipt["parent_policy_hash"] == parent.policy_hash


# ---------------------------------------------------------------------------
# Initial policy sanity
# ---------------------------------------------------------------------------


def test_initial_policy_is_valid():
    p = initial_policy()
    p.validate()  # must not raise
    assert p.status == "ACTIVE"
    assert p.generation == 0
    assert p.parent_policy_hash is None


def test_initial_policy_covers_all_16_engines():
    p = initial_policy()
    engines = {engine for wave in p.waves for engine in wave}
    assert engines == set(ENGINE_ARCHITECTURE_MIX)
    assert len(engines) == 16
