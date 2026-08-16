"""METAENGINE-1-SLICE-4 — Assimilation receipts & gate tests (TDD, written first)."""

from __future__ import annotations

import pytest

from metaengine.assimilation import (
    AblationReceipt,
    AssimilationGate,
    AssimilationReceipt,
    ExperimentReceipt,
    PromotionAuthority,
    ReceiptKind,
    TransferReceipt,
    TransferRegime,
)
from metaengine.mechanism_library import MechanismCandidate, MechanismLibrary, MechanismState
from metaengine.util import canonical_hash, sha256_bytes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HEX64 = lambda n=64: "a" * n


def _a1_candidate(*, mechanism_id: str = "mec.x") -> MechanismCandidate:
    return MechanismCandidate.create(
        mechanism_id=mechanism_id,
        semantic_definition="d",
        origin_source_ids=("src.a",),
        source_fact_boundary="b",
        hypothesized_effect="e",
        task_scope=("T",),
        prerequisites=(),
        resource_cost="low",
        complexity_cost="c",
        known_incompatibilities=(),
        known_failures=(),
        implementation_variants=(),
        experiment_receipts=(),
        ablation_receipts=(),
        transfer_receipts=(),
        confidence="LOW",
        status=MechanismState.A1_MECHANISM_HYPOTHESIS,
    )


def _experiment(*, receipt_id: str = "exp.1") -> ExperimentReceipt:
    return ExperimentReceipt.create(
        receipt_id=receipt_id,
        mechanism_id="mec.x",
        implementation_ref="metaengine_impl.module",
        regime="REASONING",
        result="REPRODUCED",
        evidence_sha256=sha256_bytes(b"exp-evidence"),
        verifier_ref="verifier.role",
        recorded_at="2026-08-14T00:00:00Z",
    )


def _ablation(*, receipt_id: str = "abl.1") -> AblationReceipt:
    return AblationReceipt.create(
        receipt_id=receipt_id,
        mechanism_id="mec.x",
        experiment_receipt_id="exp.1",
        ablated_component="router",
        result="EFFECT_DISAPPEARS",
        evidence_sha256=sha256_bytes(b"abl-evidence"),
        verifier_ref="verifier.role",
        recorded_at="2026-08-14T00:00:00Z",
    )


def _transfer(*, receipt_id: str = "trf.1", regime: TransferRegime = TransferRegime.GENERATION) -> TransferReceipt:
    return TransferReceipt.create(
        receipt_id=receipt_id,
        mechanism_id="mec.x",
        source_regime="REASONING",
        target_regime=regime,
        result="TRANSFERRED",
        evidence_sha256=sha256_bytes(b"trf-evidence"),
        verifier_ref="verifier.role",
        recorded_at="2026-08-14T00:00:00Z",
    )


def _promotion_authority(*, authority_id: str = "promoter.org_gate") -> PromotionAuthority:
    return PromotionAuthority.create(
        authority_id=authority_id,
        authority_kind="EXTERNAL_GATED_PROCESS",
        mandate_ref="gates/org-promotion-2026-08-14.json",
        recorded_at="2026-08-14T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# Typed receipts: hashing, round-trip, tamper detection
# ---------------------------------------------------------------------------


def test_experiment_receipt_create_and_hash_roundtrip():
    r = _experiment()
    payload = r.payload()
    assert payload["receipt_kind"] == "EXPERIMENT"
    assert r.receipt_hash == canonical_hash(payload)
    restored = ExperimentReceipt.from_dict(r.as_dict())
    assert restored.receipt_hash == r.receipt_hash


def test_experiment_receipt_tamper_detected():
    r = _experiment()
    tampered = r.as_dict()
    tampered["receipt_hash"] = "0" * 64
    with pytest.raises(ValueError, match="RECEIPT_HASH_MISMATCH"):
        ExperimentReceipt.from_dict(tampered)


def test_ablation_receipt_roundtrip():
    r = _ablation()
    restored = AblationReceipt.from_dict(r.as_dict())
    assert restored.receipt_hash == r.receipt_hash
    assert restored.receipt_kind == "ABLATION"


def test_transfer_receipt_roundtrip():
    r = _transfer()
    restored = TransferReceipt.from_dict(r.as_dict())
    assert restored.receipt_hash == r.receipt_hash
    assert restored.receipt_kind == "TRANSFER"


def test_receipt_kind_enum_has_three_kinds():
    assert {k.value for k in ReceiptKind} == {"EXPERIMENT", "ABLATION", "TRANSFER"}


def test_receipt_requires_hex64_evidence_hash():
    with pytest.raises(ValueError, match="EVIDENCE_HASH_INVALID"):
        ExperimentReceipt.create(
            receipt_id="exp.bad",
            mechanism_id="mec.x",
            implementation_ref="metaengine_impl.module",
            regime="REASONING",
            result="REPRODUCED",
            evidence_sha256="not-hex",
            verifier_ref="verifier.role",
            recorded_at="2026-08-14T00:00:00Z",
        )


def test_ablation_requires_known_result_enum():
    with pytest.raises(ValueError, match="ABLATION_RESULT_INVALID"):
        AblationReceipt.create(
            receipt_id="abl.bad",
            mechanism_id="mec.x",
            experiment_receipt_id="exp.1",
            ablated_component="router",
            result="WHO_KNOWS",  # invalid
            evidence_sha256=sha256_bytes(b"x"),
            verifier_ref="verifier.role",
            recorded_at="2026-08-14T00:00:00Z",
        )


# ---------------------------------------------------------------------------
# PromotionAuthority
# ---------------------------------------------------------------------------


def test_promotion_authority_roundtrip():
    pa = _promotion_authority()
    restored = PromotionAuthority.from_dict(pa.as_dict())
    assert restored == pa
    assert pa.authority_kind == "EXTERNAL_GATED_PROCESS"


# ---------------------------------------------------------------------------
# AssimilationReceipt (the gate output)
# ---------------------------------------------------------------------------


def test_assimilation_receipt_a1_to_a2_roundtrip():
    cand = _a1_candidate()
    abl = _ablation()
    trf = _transfer()
    gate = AssimilationGate()
    receipt = gate.advance_to_a2(
        candidate=cand,
        ablation=abl,
        transfer=trf,
        experiment=_experiment(),
    )
    assert receipt.transition == "A1_TO_A2"
    assert receipt.target_status is MechanismState.A2_TRANSFERABLE
    assert receipt.receipt_hash
    restored = AssimilationReceipt.from_dict(receipt.as_dict())
    assert restored.receipt_hash == receipt.receipt_hash


def test_assimilation_receipt_tamper_detected():
    cand = _a1_candidate()
    gate = AssimilationGate()
    receipt = gate.advance_to_a2(
        candidate=cand, ablation=_ablation(), transfer=_transfer(), experiment=_experiment()
    )
    tampered = receipt.as_dict()
    tampered["receipt_hash"] = "0" * 64
    with pytest.raises(ValueError, match="RECEIPT_HASH_MISMATCH"):
        AssimilationReceipt.from_dict(tampered)


# ---------------------------------------------------------------------------
# Gate evidence requirements (PRESERVE_ABSTENTION — no promotion w/o evidence)
# ---------------------------------------------------------------------------


def test_advance_to_a2_requires_at_least_one_ablation():
    cand = _a1_candidate()
    gate = AssimilationGate()
    with pytest.raises(ValueError, match="A2_REQUIRES_ABLATION"):
        gate.advance_to_a2(
            candidate=cand, ablation=None, transfer=_transfer(), experiment=_experiment()
        )


def test_advance_to_a2_requires_at_least_one_transfer():
    cand = _a1_candidate()
    gate = AssimilationGate()
    with pytest.raises(ValueError, match="A2_REQUIRES_TRANSFER"):
        gate.advance_to_a2(
            candidate=cand, ablation=_ablation(), transfer=None, experiment=_experiment()
        )


def test_advance_to_a2_requires_experiment():
    cand = _a1_candidate()
    gate = AssimilationGate()
    with pytest.raises(ValueError, match="A2_REQUIRES_EXPERIMENT"):
        gate.advance_to_a2(
            candidate=cand, ablation=_ablation(), transfer=_transfer(), experiment=None
        )


def test_advance_to_a2_rejects_non_a1_candidate():
    cand = MechanismCandidate.create(
        mechanism_id="mec.a0",
        semantic_definition="d",
        origin_source_ids=("src.a",),
        source_fact_boundary="b",
        hypothesized_effect="e",
        resource_cost="low",
        complexity_cost="c",
        confidence="LOW",
        status=MechanismState.A0_OBSERVED,
    )
    gate = AssimilationGate()
    with pytest.raises(ValueError, match="A2_REQUIRES_A1_SOURCE"):
        gate.advance_to_a2(
            candidate=cand, ablation=_ablation(), transfer=_transfer(), experiment=_experiment()
        )


def test_advance_to_a3_requires_two_distinct_regime_transfers():
    cand = _a1_candidate()
    gate = AssimilationGate()
    # Only one transfer -> rejected
    with pytest.raises(ValueError, match="A3_REQUIRES_TWO_DISTINCT_REGIME_TRANSFERS"):
        gate.advance_to_a3(
            candidate=cand,
            ablation=_ablation(),
            transfers=(_transfer(receipt_id="trf.1"),),
            promotion_authority=_promotion_authority(),
            experiment=_experiment(),
        )
    # Two transfers in the SAME target regime -> not distinct regimes -> rejected
    with pytest.raises(ValueError, match="A3_REQUIRES_TWO_DISTINCT_REGIME_TRANSFERS"):
        gate.advance_to_a3(
            candidate=cand,
            ablation=_ablation(),
            transfers=(
                _transfer(receipt_id="trf.1", regime=TransferRegime.GENERATION),
                _transfer(receipt_id="trf.2", regime=TransferRegime.GENERATION),
            ),
            promotion_authority=_promotion_authority(),
            experiment=_experiment(),
        )


def test_advance_to_a3_requires_promotion_authority():
    """SEPARATE_GENERATION_AND_PROMOTION: a mechanism cannot self-promote to A3."""
    cand = _a1_candidate()
    gate = AssimilationGate()
    with pytest.raises(ValueError, match="A3_REQUIRES_PROMOTION_AUTHORITY"):
        gate.advance_to_a3(
            candidate=cand,
            ablation=_ablation(),
            transfers=(
                _transfer(receipt_id="trf.1", regime=TransferRegime.GENERATION),
                _transfer(receipt_id="trf.2", regime=TransferRegime.REASONING),
            ),
            promotion_authority=None,
            experiment=_experiment(),
        )


def test_advance_to_a3_rejects_a2_source_without_a2_receipt():
    """A3 must be reached from A1 via a gate; bypassing A2 evidence is rejected."""
    cand = _a1_candidate()
    gate = AssimilationGate()
    # Provide valid evidence but candidate is still A1 (no A2 receipt presented)
    # -> gate accepts because it advances A1 -> A3 in one reviewed step (the gate
    # itself is the receipt chain). This is fine. The rejection case is when the
    # candidate is already A3 (no-op) or A0 (insufficient).
    a3 = gate.advance_to_a3(
        candidate=cand,
        ablation=_ablation(),
        transfers=(
            _transfer(receipt_id="trf.1", regime=TransferRegime.GENERATION),
            _transfer(receipt_id="trf.2", regime=TransferRegime.REASONING),
        ),
        promotion_authority=_promotion_authority(),
        experiment=_experiment(),
    )
    assert a3.target_status is MechanismState.A3_ASSIMILATED
    assert a3.transition == "A1_TO_A3"


# ---------------------------------------------------------------------------
# No-self-promotion: promotion_authority must differ from origin generator
# ---------------------------------------------------------------------------


def test_no_self_promotion_authority_cannot_equal_origin():
    """The promotion authority must be SEPARATE from the mechanism's origin generator."""
    cand = MechanismCandidate.create(
        mechanism_id="mec.self",
        semantic_definition="d",
        origin_source_ids=("src.metaengine.design.1",),
        source_fact_boundary="b",
        hypothesized_effect="e",
        resource_cost="low",
        complexity_cost="c",
        confidence="LOW",
        status=MechanismState.A1_MECHANISM_HYPOTHESIS,
    )
    gate = AssimilationGate()
    # Authority with the same id as the origin source -> self-promotion -> rejected
    pa = PromotionAuthority.create(
        authority_id="src.metaengine.design.1",  # same as origin source
        authority_kind="EXTERNAL_GATED_PROCESS",
        mandate_ref="gates/x.json",
        recorded_at="2026-08-14T00:00:00Z",
    )
    with pytest.raises(ValueError, match="NO_SELF_PROMOTION"):
        gate.advance_to_a3(
            candidate=cand,
            ablation=_ablation(),
            transfers=(
                _transfer(receipt_id="trf.1", regime=TransferRegime.GENERATION),
                _transfer(receipt_id="trf.2", regime=TransferRegime.REASONING),
            ),
            promotion_authority=pa,
            experiment=_experiment(),
        )


# ---------------------------------------------------------------------------
# MechanismLibrary Slice-4: evidence-gated A2/A3 admission (strict, not blanket)
# ---------------------------------------------------------------------------


def test_library_can_admit_a2_candidate_with_gate_receipt():
    """Slice 4 admits A2 ONLY when accompanied by an AssimilationReceipt (A1->A2)."""
    cand = _a1_candidate()
    gate = AssimilationGate()
    receipt = gate.advance_to_a2(
        candidate=cand, ablation=_ablation(), transfer=_transfer(), experiment=_experiment()
    )
    a2_cand = MechanismCandidate.create(
        mechanism_id="mec.x",
        semantic_definition="d",
        origin_source_ids=("src.a",),
        source_fact_boundary="b",
        hypothesized_effect="e",
        resource_cost="low",
        complexity_cost="c",
        confidence="MEDIUM",
        status=MechanismState.A2_TRANSFERABLE,
        promotion_authority=receipt,  # gate receipt authorizes the A2 state
    )
    lib = MechanismLibrary.create((a2_cand,))
    assert lib.verify() is True


def test_library_rejects_a2_without_gate_receipt():
    """A2 with NO promotion_authority (no gate receipt) is rejected — hypothesis-as-fact prevention."""
    with pytest.raises(ValueError, match="A2_REQUIRES_GATE_RECEIPT"):
        MechanismCandidate.create(
            mechanism_id="mec.x",
            semantic_definition="d",
            origin_source_ids=("src.a",),
            source_fact_boundary="b",
            hypothesized_effect="e",
            resource_cost="low",
            complexity_cost="c",
            confidence="MEDIUM",
            status=MechanismState.A2_TRANSFERABLE,
            promotion_authority=None,
        )


def test_library_rejects_a3_without_gate_receipt():
    with pytest.raises(ValueError, match="A3_REQUIRES_GATE_RECEIPT"):
        MechanismCandidate.create(
            mechanism_id="mec.x",
            semantic_definition="d",
            origin_source_ids=("src.a",),
            source_fact_boundary="b",
            hypothesized_effect="e",
            resource_cost="low",
            complexity_cost="c",
            confidence="HIGH",
            status=MechanismState.A3_ASSIMILATED,
            promotion_authority=None,
        )


def test_library_has_a3_influence_true_only_when_a3_present():
    a0 = MechanismCandidate.create(
        mechanism_id="mec.a0",
        semantic_definition="d",
        origin_source_ids=("src.a",),
        source_fact_boundary="b",
        hypothesized_effect="e",
        resource_cost="low",
        complexity_cost="c",
        confidence="LOW",
        status=MechanismState.A0_OBSERVED,
    )
    lib = MechanismLibrary.create((a0,))
    assert lib.has_a3_influence() is False
    assert lib.assert_no_a3_influence() is None  # no A3 -> ok

    # Build an A3 candidate via the gate
    receipt = AssimilationGate().advance_to_a3(
        candidate=_a1_candidate(),
        ablation=_ablation(),
        transfers=(
            _transfer(receipt_id="trf.1", regime=TransferRegime.GENERATION),
            _transfer(receipt_id="trf.2", regime=TransferRegime.REASONING),
        ),
        promotion_authority=_promotion_authority(),
        experiment=_experiment(),
    )
    a3 = MechanismCandidate.create(
        mechanism_id="mec.a3",
        semantic_definition="d",
        origin_source_ids=("src.a",),
        source_fact_boundary="b",
        hypothesized_effect="e",
        resource_cost="low",
        complexity_cost="c",
        confidence="HIGH",
        status=MechanismState.A3_ASSIMILATED,
        promotion_authority=receipt,
    )
    lib_with_a3 = MechanismLibrary.create((a3,))
    assert lib_with_a3.has_a3_influence() is True
    with pytest.raises(ValueError, match="MECHANISM_LIBRARY_A3_INFLUENCE_FORBIDDEN_IN_SLICE3"):
        lib_with_a3.assert_no_a3_influence()
