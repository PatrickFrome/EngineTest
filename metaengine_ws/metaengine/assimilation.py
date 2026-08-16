"""METAENGINE-1-SLICE-4 — Assimilation receipts and gate.

Implements the evidence-gated mechanism assimilation path (spec §10.2, §11):

    A0_OBSERVED  -> A1_MECHANISM_HYPOTHESIS  (Slice 3)
    A1           -> A2_TRANSFERABLE          (gate: experiment + ablation + transfer)
    A1           -> A3_ASSIMILATED           (gate: experiment + ablation + 2 distinct-regime transfers + separate promotion authority)

Constitutional guarantees:

* ``PRESERVE_ABSTENTION`` — no transition to A2/A3 without real evidence
  (experiment receipt, ablation receipt, transfer receipt(s)).
* ``MUTATION_REQUIRES_RECEIPT`` — every transition produces a content-addressed
  :class:`AssimilationReceipt`; ``from_dict`` re-verifies the claimed hash.
* ``SEPARATE_GENERATION_AND_PROMOTION`` — A3 requires a
  :class:`PromotionAuthority` whose ``authority_id`` differs from every
  ``origin_source_id`` of the candidate (no self-promotion).  Only A3 may
  automatically influence organization-policy generation.
* ``FROZEN_EVALUATION_CONTRACT`` — receipts pin regime, evidence_hash,
  verifier_ref.

The receipts are content-addressed frozen dataclasses following the
Slice-2/3 pattern (``create()`` / ``payload()`` / ``receipt_hash`` via
:func:`canonical_hash` / ``from_dict()`` claimed-hash re-verification).
"""

from __future__ import annotations

import string
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from .mechanism_library import MechanismCandidate, MechanismState
from .util import canonical_hash


ASSIMILATION_PROTOCOL_VERSION = "METAENGINE-ASSIMILATION-1"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ReceiptKind(str, Enum):
    EXPERIMENT = "EXPERIMENT"
    ABLATION = "ABLATION"
    TRANSFER = "TRANSFER"


class TransferRegime(str, Enum):
    GENERATION = "GENERATION"
    REASONING = "REASONING"
    RETRIEVAL = "RETRIEVAL"
    PLANNING = "PLANNING"
    AGENTIC = "AGENTIC"
    TESTING = "TESTING"
    MULTI_WAVE = "MULTI_WAVE"
    LONG_CONTEXT = "LONG_CONTEXT"


class ExperimentResult(str, Enum):
    REPRODUCED = "REPRODUCED"
    NOT_REPRODUCED = "NOT_REPRODUCED"
    INCONCLUSIVE = "INCONCLUSIVE"


class AblationResult(str, Enum):
    EFFECT_DISAPPEARS = "EFFECT_DISAPPEARS"
    EFFECT_PERSISTS = "EFFECT_PERSISTS"
    EFFECT_PARTIALLY_DIMINISHES = "EFFECT_PARTIALLY_DIMINISHES"


class TransferResult(str, Enum):
    TRANSFERRED = "TRANSFERRED"
    NOT_TRANSFERRED = "NOT_TRANSFERRED"
    PARTIAL_TRANSFER = "PARTIAL_TRANSFER"


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _is_hex(value: str, length: int) -> bool:
    return len(value) == length and all(ch in string.hexdigits for ch in value)


def _text(value: object, code: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(code)
    return result


def _require_hex64(value: object, code: str) -> str:
    text = str(value).strip()
    if not _is_hex(text, 64):
        raise ValueError(code)
    return text


# ---------------------------------------------------------------------------
# ExperimentReceipt
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExperimentReceipt:
    receipt_id: str
    mechanism_id: str
    implementation_ref: str
    regime: str
    result: ExperimentResult
    evidence_sha256: str
    verifier_ref: str
    recorded_at: str

    @classmethod
    def create(
        cls,
        *,
        receipt_id: str,
        mechanism_id: str,
        implementation_ref: str,
        regime: str,
        result: ExperimentResult | str,
        evidence_sha256: str,
        verifier_ref: str,
        recorded_at: str,
    ) -> "ExperimentReceipt":
        item = cls(
            receipt_id=_text(receipt_id, "RECEIPT_ID_REQUIRED"),
            mechanism_id=_text(mechanism_id, "MECHANISM_ID_REQUIRED"),
            implementation_ref=_text(implementation_ref, "IMPLEMENTATION_REF_REQUIRED"),
            regime=_text(regime, "REGIME_REQUIRED"),
            result=ExperimentResult(result),
            evidence_sha256=_require_hex64(evidence_sha256, "EVIDENCE_HASH_INVALID"),
            verifier_ref=_text(verifier_ref, "VERIFIER_REF_REQUIRED"),
            recorded_at=_text(recorded_at, "RECORDED_AT_REQUIRED"),
        )
        return item

    def payload(self) -> dict[str, Any]:
        return {
            "receipt_kind": ReceiptKind.EXPERIMENT.value,
            "receipt_version": ASSIMILATION_PROTOCOL_VERSION,
            "receipt_id": self.receipt_id,
            "mechanism_id": self.mechanism_id,
            "implementation_ref": self.implementation_ref,
            "regime": self.regime,
            "result": self.result.value,
            "evidence_sha256": self.evidence_sha256,
            "verifier_ref": self.verifier_ref,
            "recorded_at": self.recorded_at,
        }

    @property
    def receipt_kind(self) -> str:
        return ReceiptKind.EXPERIMENT.value

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.payload())

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_hash": self.receipt_hash}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ExperimentReceipt":
        item = cls.create(
            receipt_id=str(value["receipt_id"]),
            mechanism_id=str(value["mechanism_id"]),
            implementation_ref=str(value["implementation_ref"]),
            regime=str(value["regime"]),
            result=ExperimentResult(str(value["result"])),
            evidence_sha256=str(value["evidence_sha256"]),
            verifier_ref=str(value["verifier_ref"]),
            recorded_at=str(value["recorded_at"]),
        )
        claimed = value.get("receipt_hash")
        if claimed is not None and str(claimed) != item.receipt_hash:
            raise ValueError("RECEIPT_HASH_MISMATCH")
        return item


# ---------------------------------------------------------------------------
# AblationReceipt
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AblationReceipt:
    receipt_id: str
    mechanism_id: str
    experiment_receipt_id: str
    ablated_component: str
    result: AblationResult
    evidence_sha256: str
    verifier_ref: str
    recorded_at: str

    @classmethod
    def create(
        cls,
        *,
        receipt_id: str,
        mechanism_id: str,
        experiment_receipt_id: str,
        ablated_component: str,
        result: AblationResult | str,
        evidence_sha256: str,
        verifier_ref: str,
        recorded_at: str,
    ) -> "AblationReceipt":
        try:
            abl_result = AblationResult(result)
        except ValueError:
            raise ValueError("ABLATION_RESULT_INVALID")
        item = cls(
            receipt_id=_text(receipt_id, "RECEIPT_ID_REQUIRED"),
            mechanism_id=_text(mechanism_id, "MECHANISM_ID_REQUIRED"),
            experiment_receipt_id=_text(experiment_receipt_id, "EXPERIMENT_RECEIPT_ID_REQUIRED"),
            ablated_component=_text(ablated_component, "ABLATED_COMPONENT_REQUIRED"),
            result=abl_result,
            evidence_sha256=_require_hex64(evidence_sha256, "EVIDENCE_HASH_INVALID"),
            verifier_ref=_text(verifier_ref, "VERIFIER_REF_REQUIRED"),
            recorded_at=_text(recorded_at, "RECORDED_AT_REQUIRED"),
        )
        return item

    def payload(self) -> dict[str, Any]:
        return {
            "receipt_kind": ReceiptKind.ABLATION.value,
            "receipt_version": ASSIMILATION_PROTOCOL_VERSION,
            "receipt_id": self.receipt_id,
            "mechanism_id": self.mechanism_id,
            "experiment_receipt_id": self.experiment_receipt_id,
            "ablated_component": self.ablated_component,
            "result": self.result.value,
            "evidence_sha256": self.evidence_sha256,
            "verifier_ref": self.verifier_ref,
            "recorded_at": self.recorded_at,
        }

    @property
    def receipt_kind(self) -> str:
        return ReceiptKind.ABLATION.value

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.payload())

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_hash": self.receipt_hash}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AblationReceipt":
        item = cls.create(
            receipt_id=str(value["receipt_id"]),
            mechanism_id=str(value["mechanism_id"]),
            experiment_receipt_id=str(value["experiment_receipt_id"]),
            ablated_component=str(value["ablated_component"]),
            result=str(value["result"]),
            evidence_sha256=str(value["evidence_sha256"]),
            verifier_ref=str(value["verifier_ref"]),
            recorded_at=str(value["recorded_at"]),
        )
        claimed = value.get("receipt_hash")
        if claimed is not None and str(claimed) != item.receipt_hash:
            raise ValueError("RECEIPT_HASH_MISMATCH")
        return item


# ---------------------------------------------------------------------------
# TransferReceipt
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TransferReceipt:
    receipt_id: str
    mechanism_id: str
    source_regime: TransferRegime
    target_regime: TransferRegime
    result: TransferResult
    evidence_sha256: str
    verifier_ref: str
    recorded_at: str

    @classmethod
    def create(
        cls,
        *,
        receipt_id: str,
        mechanism_id: str,
        source_regime: TransferRegime | str,
        target_regime: TransferRegime | str,
        result: TransferResult | str,
        evidence_sha256: str,
        verifier_ref: str,
        recorded_at: str,
    ) -> "TransferReceipt":
        item = cls(
            receipt_id=_text(receipt_id, "RECEIPT_ID_REQUIRED"),
            mechanism_id=_text(mechanism_id, "MECHANISM_ID_REQUIRED"),
            source_regime=TransferRegime(source_regime),
            target_regime=TransferRegime(target_regime),
            result=TransferResult(result),
            evidence_sha256=_require_hex64(evidence_sha256, "EVIDENCE_HASH_INVALID"),
            verifier_ref=_text(verifier_ref, "VERIFIER_REF_REQUIRED"),
            recorded_at=_text(recorded_at, "RECORDED_AT_REQUIRED"),
        )
        return item

    def payload(self) -> dict[str, Any]:
        return {
            "receipt_kind": ReceiptKind.TRANSFER.value,
            "receipt_version": ASSIMILATION_PROTOCOL_VERSION,
            "receipt_id": self.receipt_id,
            "mechanism_id": self.mechanism_id,
            "source_regime": self.source_regime.value,
            "target_regime": self.target_regime.value,
            "result": self.result.value,
            "evidence_sha256": self.evidence_sha256,
            "verifier_ref": self.verifier_ref,
            "recorded_at": self.recorded_at,
        }

    @property
    def receipt_kind(self) -> str:
        return ReceiptKind.TRANSFER.value

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.payload())

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_hash": self.receipt_hash}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TransferReceipt":
        item = cls.create(
            receipt_id=str(value["receipt_id"]),
            mechanism_id=str(value["mechanism_id"]),
            source_regime=str(value["source_regime"]),
            target_regime=str(value["target_regime"]),
            result=str(value["result"]),
            evidence_sha256=str(value["evidence_sha256"]),
            verifier_ref=str(value["verifier_ref"]),
            recorded_at=str(value["recorded_at"]),
        )
        claimed = value.get("receipt_hash")
        if claimed is not None and str(claimed) != item.receipt_hash:
            raise ValueError("RECEIPT_HASH_MISMATCH")
        return item


# ---------------------------------------------------------------------------
# PromotionAuthority (SEPARATE_GENERATION_AND_PROMOTION)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PromotionAuthority:
    authority_id: str
    authority_kind: str
    mandate_ref: str
    recorded_at: str

    @classmethod
    def create(
        cls,
        *,
        authority_id: str,
        authority_kind: str,
        mandate_ref: str,
        recorded_at: str,
    ) -> "PromotionAuthority":
        item = cls(
            authority_id=_text(authority_id, "AUTHORITY_ID_REQUIRED"),
            authority_kind=_text(authority_kind, "AUTHORITY_KIND_REQUIRED"),
            mandate_ref=_text(mandate_ref, "MANDATE_REF_REQUIRED"),
            recorded_at=_text(recorded_at, "RECORDED_AT_REQUIRED"),
        )
        return item

    def payload(self) -> dict[str, Any]:
        return {
            "authority_id": self.authority_id,
            "authority_kind": self.authority_kind,
            "mandate_ref": self.mandate_ref,
            "recorded_at": self.recorded_at,
        }

    def as_dict(self) -> dict[str, Any]:
        return self.payload()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PromotionAuthority":
        return cls.create(
            authority_id=str(value["authority_id"]),
            authority_kind=str(value["authority_kind"]),
            mandate_ref=str(value["mandate_ref"]),
            recorded_at=str(value["recorded_at"]),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PromotionAuthority):
            return NotImplemented
        return self.payload() == other.payload()

    def __hash__(self) -> int:
        return hash(canonical_hash(self.payload()))


# ---------------------------------------------------------------------------
# AssimilationReceipt (the gate output — content-addressed)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AssimilationReceipt:
    transition: str
    mechanism_id: str
    source_status: MechanismState
    target_status: MechanismState
    experiment_receipt_hash: str
    ablation_receipt_hash: str
    transfer_receipt_hashes: tuple[str, ...]
    promotion_authority: PromotionAuthority | None
    recorded_at: str

    def payload(self) -> dict[str, Any]:
        return {
            "receipt_kind": "ASSIMILATION",
            "receipt_version": ASSIMILATION_PROTOCOL_VERSION,
            "transition": self.transition,
            "mechanism_id": self.mechanism_id,
            "source_status": self.source_status.value,
            "target_status": self.target_status.value,
            "experiment_receipt_hash": self.experiment_receipt_hash,
            "ablation_receipt_hash": self.ablation_receipt_hash,
            "transfer_receipt_hashes": list(self.transfer_receipt_hashes),
            "promotion_authority": (
                self.promotion_authority.payload() if self.promotion_authority else None
            ),
            "recorded_at": self.recorded_at,
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.payload())

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "receipt_hash": self.receipt_hash}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AssimilationReceipt":
        pa_raw = value.get("promotion_authority")
        pa = PromotionAuthority.from_dict(pa_raw) if pa_raw else None
        item = cls(
            transition=str(value["transition"]),
            mechanism_id=str(value["mechanism_id"]),
            source_status=MechanismState(str(value["source_status"])),
            target_status=MechanismState(str(value["target_status"])),
            experiment_receipt_hash=str(value["experiment_receipt_hash"]),
            ablation_receipt_hash=str(value["ablation_receipt_hash"]),
            transfer_receipt_hashes=tuple(value.get("transfer_receipt_hashes", ())),
            promotion_authority=pa,
            recorded_at=str(value["recorded_at"]),
        )
        claimed = value.get("receipt_hash")
        if claimed is not None and str(claimed) != item.receipt_hash:
            raise ValueError("RECEIPT_HASH_MISMATCH")
        return item


# ---------------------------------------------------------------------------
# AssimilationGate
# ---------------------------------------------------------------------------


class AssimilationGate:
    """Produces content-addressed AssimilationReceipts for A1->A2 and A1->A3.

    The gate enforces evidence requirements (PRESERVE_ABSTENTION) and the
    separate-promotion-authority rule (SEPARATE_GENERATION_AND_PROMOTION).
    """

    def advance_to_a2(
        self,
        *,
        candidate: MechanismCandidate,
        ablation: AblationReceipt | None,
        transfer: TransferReceipt | None,
        experiment: ExperimentReceipt | None,
        recorded_at: str | None = None,
    ) -> AssimilationReceipt:
        if MechanismState(candidate.status) is not MechanismState.A1_MECHANISM_HYPOTHESIS:
            raise ValueError("A2_REQUIRES_A1_SOURCE")
        if experiment is None:
            raise ValueError("A2_REQUIRES_EXPERIMENT")
        if ablation is None:
            raise ValueError("A2_REQUIRES_ABLATION")
        if transfer is None:
            raise ValueError("A2_REQUIRES_TRANSFER")

        ts = recorded_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return AssimilationReceipt(
            transition="A1_TO_A2",
            mechanism_id=candidate.mechanism_id,
            source_status=MechanismState.A1_MECHANISM_HYPOTHESIS,
            target_status=MechanismState.A2_TRANSFERABLE,
            experiment_receipt_hash=experiment.receipt_hash,
            ablation_receipt_hash=ablation.receipt_hash,
            transfer_receipt_hashes=(transfer.receipt_hash,),
            promotion_authority=None,
            recorded_at=ts,
        )

    def advance_to_a3(
        self,
        *,
        candidate: MechanismCandidate,
        ablation: AblationReceipt | None,
        transfers: Iterable[TransferReceipt],
        promotion_authority: PromotionAuthority | None,
        experiment: ExperimentReceipt | None,
        recorded_at: str | None = None,
    ) -> AssimilationReceipt:
        if MechanismState(candidate.status) is not MechanismState.A1_MECHANISM_HYPOTHESIS:
            raise ValueError("A3_REQUIRES_A1_SOURCE")
        if experiment is None:
            raise ValueError("A3_REQUIRES_EXPERIMENT")
        if ablation is None:
            raise ValueError("A3_REQUIRES_ABLATION")

        transfer_list = tuple(transfers)
        distinct_regimes = {
            t.target_regime for t in transfer_list if t is not None
        }
        if len(transfer_list) < 2 or len(distinct_regimes) < 2:
            raise ValueError("A3_REQUIRES_TWO_DISTINCT_REGIME_TRANSFERS")

        if promotion_authority is None:
            raise ValueError("A3_REQUIRES_PROMOTION_AUTHORITY")

        # NO_SELF_PROMOTION: the promotion authority must be SEPARATE from the
        # mechanism's origin generator (origin_source_ids).
        if promotion_authority.authority_id in set(candidate.origin_source_ids):
            raise ValueError("NO_SELF_PROMOTION")

        ts = recorded_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        transfer_hashes = tuple(sorted({t.receipt_hash for t in transfer_list}))
        return AssimilationReceipt(
            transition="A1_TO_A3",
            mechanism_id=candidate.mechanism_id,
            source_status=MechanismState.A1_MECHANISM_HYPOTHESIS,
            target_status=MechanismState.A3_ASSIMILATED,
            experiment_receipt_hash=experiment.receipt_hash,
            ablation_receipt_hash=ablation.receipt_hash,
            transfer_receipt_hashes=transfer_hashes,
            promotion_authority=promotion_authority,
            recorded_at=ts,
        )
