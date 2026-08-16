from __future__ import annotations

import json

import pytest

from metaengine.mechanism_library import (
    MechanismCandidate,
    MechanismLibrary,
    MechanismState,
    MECHANISM_LIBRARY_VERSION,
)
from metaengine.util import canonical_hash


def _candidate(
    *,
    mechanism_id: str = "mec.sparse_conditional_routing",
    status: MechanismState = MechanismState.A0_OBSERVED,
) -> MechanismCandidate:
    return MechanismCandidate.create(
        mechanism_id=mechanism_id,
        semantic_definition="Route only a subset of experts/paths per token based on a learned gate.",
        origin_source_ids=("src.deepseek.1", "src.qwen.1"),
        source_fact_boundary="Source papers report the routing pattern; the exact gate implementation is source code only where permissively licensed.",
        hypothesized_effect="Reduces per-token compute without proportional quality loss under bounded load.",
        task_scope=("GENERATION", "MIXED_RETRIEVAL"),
        prerequisites=("learned_router_weights",),
        resource_cost="UNOBSERVED",
        complexity_cost="moderate router + load balancing",
        known_incompatibilities=("strict-determinism pipelines",),
        known_failures=(),
        implementation_variants=("top-1-router", "top-2-router"),
        experiment_receipts=(),
        ablation_receipts=(),
        transfer_receipts=(),
        confidence="UNOBSERVED",
        status=status,
    )


# ---------------------------------------------------------------------------
# MechanismState enum & Slice-3 admission guard
# ---------------------------------------------------------------------------


def test_mechanism_state_enum_has_four_states():
    assert {s.value for s in MechanismState} == {
        "A0_OBSERVED",
        "A1_MECHANISM_HYPOTHESIS",
        "A2_TRANSFERABLE",
        "A3_ASSIMILATED",
    }


def test_slice3_admits_a0_and_a1_only():
    a0 = _candidate(status=MechanismState.A0_OBSERVED)
    a1 = _candidate(status=MechanismState.A1_MECHANISM_HYPOTHESIS)
    assert a0.status is MechanismState.A0_OBSERVED
    assert a1.status is MechanismState.A1_MECHANISM_HYPOTHESIS


def test_slice4_rejects_a2_without_gate_receipt():
    """Slice 4: A2 is admissible ONLY with a gate receipt (AssimilationReceipt).
    Without evidence, creation is rejected — hypothesis-as-fact prevention."""
    with pytest.raises(ValueError, match="A2_REQUIRES_GATE_RECEIPT"):
        _candidate(status=MechanismState.A2_TRANSFERABLE)


def test_slice4_rejects_a3_without_gate_receipt():
    """Slice 4: A3 is admissible ONLY with a gate receipt + promotion authority."""
    with pytest.raises(ValueError, match="A3_REQUIRES_GATE_RECEIPT"):
        _candidate(status=MechanismState.A3_ASSIMILATED)


# ---------------------------------------------------------------------------
# Candidate hashing & round-trip
# ---------------------------------------------------------------------------


def test_candidate_create_and_hash_roundtrip():
    c = _candidate()
    payload = c.payload()
    assert payload["status"] == "A0_OBSERVED"
    assert c.mechanism_hash == canonical_hash(payload)
    restored = MechanismCandidate.from_dict(c.as_dict())
    assert restored.mechanism_hash == c.mechanism_hash


def test_candidate_from_dict_rejects_tampered_hash():
    c = _candidate()
    tampered = c.as_dict()
    tampered["mechanism_hash"] = "0" * 64
    with pytest.raises(ValueError, match="MECHANISM_HASH_MISMATCH"):
        MechanismCandidate.from_dict(tampered)


def test_candidate_requires_origin_source_ids():
    with pytest.raises(ValueError, match="ORIGIN_SOURCE_IDS_REQUIRED"):
        MechanismCandidate.create(
            mechanism_id="mec.x",
            semantic_definition="d",
            origin_source_ids=(),  # empty -> rejected
            source_fact_boundary="b",
            hypothesized_effect="e",
            task_scope=("T",),
            prerequisites=(),
            resource_cost="UNOBSERVED",
            complexity_cost="c",
            known_incompatibilities=(),
            known_failures=(),
            implementation_variants=(),
            experiment_receipts=(),
            ablation_receipts=(),
            transfer_receipts=(),
            confidence="UNOBSERVED",
            status=MechanismState.A0_OBSERVED,
        )


def test_candidate_receipt_hashes_must_be_hex():
    with pytest.raises(ValueError, match="RECEIPT_HASH_INVALID"):
        MechanismCandidate.create(
            mechanism_id="mec.x",
            semantic_definition="d",
            origin_source_ids=("src.a",),
            source_fact_boundary="b",
            hypothesized_effect="e",
            task_scope=("T",),
            prerequisites=(),
            resource_cost="UNOBSERVED",
            complexity_cost="c",
            known_incompatibilities=(),
            known_failures=(),
            implementation_variants=(),
            experiment_receipts=("not-hex",),  # invalid
            ablation_receipts=(),
            transfer_receipts=(),
            confidence="UNOBSERVED",
            status=MechanismState.A0_OBSERVED,
        )


# ---------------------------------------------------------------------------
# MechanismLibrary collection
# ---------------------------------------------------------------------------


def test_library_deterministic_regardless_of_input_order():
    a = _candidate(mechanism_id="mec.a")
    b = _candidate(mechanism_id="mec.b")
    l1 = MechanismLibrary.create((a, b))
    l2 = MechanismLibrary.create((b, a))
    assert l1.library_hash == l2.library_hash
    assert [c.mechanism_id for c in l1.candidates] == ["mec.a", "mec.b"]


def test_library_rejects_duplicate_mechanism_id():
    a = _candidate(mechanism_id="mec.dup")
    b = _candidate(mechanism_id="mec.dup")
    with pytest.raises(ValueError, match="MECHANISM_ID_DUPLICATE"):
        MechanismLibrary.create((a, b))


def test_library_from_dict_roundtrip():
    a = _candidate(mechanism_id="mec.a")
    b = _candidate(mechanism_id="mec.b", status=MechanismState.A1_MECHANISM_HYPOTHESIS)
    lib = MechanismLibrary.create((a, b))
    blob = json.dumps(lib.as_dict(), sort_keys=True)
    restored = MechanismLibrary.from_dict(json.loads(blob))
    assert restored.library_hash == lib.library_hash
    assert restored.verify() is True


def test_library_asserts_no_a3_influence_in_slice3():
    # Slice 3 must not let any A3 candidate influence organization generation.
    a = _candidate(mechanism_id="mec.a")
    lib = MechanismLibrary.create((a,))
    # All candidates are A0/A1 -> no A3 influence -> assertion passes
    lib.assert_no_a3_influence()
    assert lib.has_a3_influence() is False


def test_library_version_constant():
    assert MECHANISM_LIBRARY_VERSION == "METAENGINE-MECHANISM-LIBRARY-1"
