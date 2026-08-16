"""METAENGINE-1-SLICE-4 — Mechanism Library (full A0-A3 state machine).

MetaEngine assimilates **mechanisms**, not brands, model weights, or whole
foreign architectures (spec section 10.1).  A mechanism is an abstract,
independently implementable hypothesis about a causal organization or
computation strategy.

Mechanism states (spec section 10.2)::

    A0_OBSERVED              — an interesting property/behavior is observed.
    A1_MECHANISM_HYPOTHESIS  — a plausible abstract mechanism identified.
    A2_TRANSFERABLE          — independent MetaEngine implementation reproduces
                               the effect and survives ablation.
    A3_ASSIMILATED           — transfers across regimes and MAY influence
                               organization generation/search.

Slice 4 extends the Slice-3 A0/A1-only library to the full A0-A3 state
machine with **evidence-gated admission**:

* A0/A1 require no gate receipt (hypothesis stage).
* A2/A3 require a :class:`~metaengine.assimilation.AssimilationReceipt`
  (produced by :class:`~metaengine.assimilation.AssimilationGate`) stored in
  the ``promotion_authority`` field.  Without it, creation is rejected
  (``A2_REQUIRES_GATE_RECEIPT`` / ``A3_REQUIRES_GATE_RECEIPT``).

Only ``A3_ASSIMILATED`` may automatically influence future
organization-policy generation; the ``SEPARATE_GENERATION_AND_PROMOTION``
constitutional invariant is preserved by the gate's no-self-promotion check
and by :meth:`MechanismLibrary.assert_no_a3_influence`.
"""

from __future__ import annotations

import string
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from .util import canonical_hash


MECHANISM_LIBRARY_VERSION = "METAENGINE-MECHANISM-LIBRARY-1"


class MechanismState(str, Enum):
    A0_OBSERVED = "A0_OBSERVED"
    A1_MECHANISM_HYPOTHESIS = "A1_MECHANISM_HYPOTHESIS"
    A2_TRANSFERABLE = "A2_TRANSFERABLE"
    A3_ASSIMILATED = "A3_ASSIMILATED"


def _is_hex(value: str, length: int) -> bool:
    return len(value) == length and all(ch in string.hexdigits for ch in value)


def _text(value: object, code: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(code)
    return result


def _strings(values: Iterable[object], *, code: str) -> tuple[str, ...]:
    return tuple(sorted({_text(value, code) for value in values}))


def _receipt_hashes(values: Iterable[object], *, code: str) -> tuple[str, ...]:
    result = tuple(sorted({str(v).strip() for v in values if str(v).strip()}))
    if any(not _is_hex(v, 64) for v in result):
        raise ValueError(code)
    return result


def _deserialize_promotion_authority(value: object) -> Any:
    """Lazy-deserialize an AssimilationReceipt from a dict (avoids circular import).

    Returns None if ``value`` is None.  Otherwise imports
    :class:`~metaengine.assimilation.AssimilationReceipt` at call time and
    reconstructs it (which re-verifies the claimed hash).
    """
    if value is None:
        return None
    from .assimilation import AssimilationReceipt  # lazy: avoids circular import

    return AssimilationReceipt.from_dict(value)


# ---------------------------------------------------------------------------
# MechanismCandidate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MechanismCandidate:
    mechanism_id: str
    semantic_definition: str
    origin_source_ids: tuple[str, ...]
    source_fact_boundary: str
    hypothesized_effect: str
    task_scope: tuple[str, ...]
    prerequisites: tuple[str, ...]
    resource_cost: str
    complexity_cost: str
    known_incompatibilities: tuple[str, ...]
    known_failures: tuple[str, ...]
    implementation_variants: tuple[str, ...]
    experiment_receipts: tuple[str, ...]
    ablation_receipts: tuple[str, ...]
    transfer_receipts: tuple[str, ...]
    confidence: str
    status: MechanismState
    promotion_authority: Any  # AssimilationReceipt | None (lazy-typed to avoid circular import)

    @classmethod
    def create(
        cls,
        *,
        mechanism_id: str,
        semantic_definition: str,
        origin_source_ids: Iterable[str],
        source_fact_boundary: str,
        hypothesized_effect: str,
        task_scope: Iterable[str] = (),
        prerequisites: Iterable[str] = (),
        resource_cost: str,
        complexity_cost: str,
        known_incompatibilities: Iterable[str] = (),
        known_failures: Iterable[str] = (),
        implementation_variants: Iterable[str] = (),
        experiment_receipts: Iterable[str] = (),
        ablation_receipts: Iterable[str] = (),
        transfer_receipts: Iterable[str] = (),
        confidence: str,
        status: MechanismState | str,
        promotion_authority: Any = None,
    ) -> "MechanismCandidate":
        status = MechanismState(status)
        # Slice 4: A2/A3 are admissible ONLY with a gate receipt (AssimilationReceipt).
        # Without evidence, creation is rejected (hypothesis-as-fact prevention).
        if status is MechanismState.A2_TRANSFERABLE and promotion_authority is None:
            raise ValueError("A2_REQUIRES_GATE_RECEIPT")
        if status is MechanismState.A3_ASSIMILATED and promotion_authority is None:
            raise ValueError("A3_REQUIRES_GATE_RECEIPT")

        origins = _strings(origin_source_ids, code="ORIGIN_SOURCE_ID_INVALID")
        if not origins:
            raise ValueError("ORIGIN_SOURCE_IDS_REQUIRED")

        item = cls(
            mechanism_id=_text(mechanism_id, "MECHANISM_ID_REQUIRED"),
            semantic_definition=_text(semantic_definition, "MECHANISM_DEFINITION_REQUIRED"),
            origin_source_ids=origins,
            source_fact_boundary=_text(source_fact_boundary, "MECHANISM_FACT_BOUNDARY_REQUIRED"),
            hypothesized_effect=_text(hypothesized_effect, "MECHANISM_EFFECT_REQUIRED"),
            task_scope=_strings(task_scope, code="MECHANISM_TASK_SCOPE_INVALID"),
            prerequisites=_strings(prerequisites, code="MECHANISM_PREREQ_INVALID"),
            resource_cost=_text(resource_cost, "MECHANISM_RESOURCE_COST_REQUIRED"),
            complexity_cost=_text(complexity_cost, "MECHANISM_COMPLEXITY_COST_REQUIRED"),
            known_incompatibilities=_strings(known_incompatibilities, code="MECHANISM_INCOMPAT_INVALID"),
            known_failures=_strings(known_failures, code="MECHANISM_FAILURE_INVALID"),
            implementation_variants=_strings(implementation_variants, code="MECHANISM_VARIANT_INVALID"),
            experiment_receipts=_receipt_hashes(experiment_receipts, code="RECEIPT_HASH_INVALID"),
            ablation_receipts=_receipt_hashes(ablation_receipts, code="RECEIPT_HASH_INVALID"),
            transfer_receipts=_receipt_hashes(transfer_receipts, code="RECEIPT_HASH_INVALID"),
            confidence=_text(confidence, "MECHANISM_CONFIDENCE_REQUIRED"),
            status=status,
            promotion_authority=promotion_authority,
        )
        item.validate()
        return item

    def validate(self) -> None:
        _text(self.mechanism_id, "MECHANISM_ID_REQUIRED")
        _text(self.semantic_definition, "MECHANISM_DEFINITION_REQUIRED")
        _text(self.source_fact_boundary, "MECHANISM_FACT_BOUNDARY_REQUIRED")
        _text(self.hypothesized_effect, "MECHANISM_EFFECT_REQUIRED")
        _text(self.resource_cost, "MECHANISM_RESOURCE_COST_REQUIRED")
        _text(self.complexity_cost, "MECHANISM_COMPLEXITY_COST_REQUIRED")
        _text(self.confidence, "MECHANISM_CONFIDENCE_REQUIRED")
        if not self.origin_source_ids:
            raise ValueError("ORIGIN_SOURCE_IDS_REQUIRED")
        status = MechanismState(self.status)
        if status is MechanismState.A2_TRANSFERABLE and self.promotion_authority is None:
            raise ValueError("A2_REQUIRES_GATE_RECEIPT")
        if status is MechanismState.A3_ASSIMILATED and self.promotion_authority is None:
            raise ValueError("A3_REQUIRES_GATE_RECEIPT")
        for field in (
            self.experiment_receipts,
            self.ablation_receipts,
            self.transfer_receipts,
        ):
            for value in field:
                if not _is_hex(value, 64):
                    raise ValueError("RECEIPT_HASH_INVALID")

    def payload(self) -> dict[str, Any]:
        self.validate()
        return {
            "library_version": MECHANISM_LIBRARY_VERSION,
            "mechanism_id": self.mechanism_id,
            "semantic_definition": self.semantic_definition,
            "origin_source_ids": list(self.origin_source_ids),
            "source_fact_boundary": self.source_fact_boundary,
            "hypothesized_effect": self.hypothesized_effect,
            "task_scope": list(self.task_scope),
            "prerequisites": list(self.prerequisites),
            "resource_cost": self.resource_cost,
            "complexity_cost": self.complexity_cost,
            "known_incompatibilities": list(self.known_incompatibilities),
            "known_failures": list(self.known_failures),
            "implementation_variants": list(self.implementation_variants),
            "experiment_receipts": list(self.experiment_receipts),
            "ablation_receipts": list(self.ablation_receipts),
            "transfer_receipts": list(self.transfer_receipts),
            "confidence": self.confidence,
            "status": self.status.value,
            "promotion_authority": (
                self.promotion_authority.as_dict() if self.promotion_authority else None
            ),
        }

    @property
    def mechanism_hash(self) -> str:
        return canonical_hash(self.payload())

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "mechanism_hash": self.mechanism_hash}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MechanismCandidate":
        item = cls(
            mechanism_id=str(value["mechanism_id"]),
            semantic_definition=str(value["semantic_definition"]),
            origin_source_ids=tuple(value.get("origin_source_ids", ())),
            source_fact_boundary=str(value["source_fact_boundary"]),
            hypothesized_effect=str(value["hypothesized_effect"]),
            task_scope=tuple(value.get("task_scope", ())),
            prerequisites=tuple(value.get("prerequisites", ())),
            resource_cost=str(value["resource_cost"]),
            complexity_cost=str(value["complexity_cost"]),
            known_incompatibilities=tuple(value.get("known_incompatibilities", ())),
            known_failures=tuple(value.get("known_failures", ())),
            implementation_variants=tuple(value.get("implementation_variants", ())),
            experiment_receipts=tuple(value.get("experiment_receipts", ())),
            ablation_receipts=tuple(value.get("ablation_receipts", ())),
            transfer_receipts=tuple(value.get("transfer_receipts", ())),
            confidence=str(value["confidence"]),
            status=MechanismState(str(value["status"])),
            promotion_authority=_deserialize_promotion_authority(
                value.get("promotion_authority")
            ),
        )
        item.validate()
        claimed = value.get("mechanism_hash")
        if claimed is not None and str(claimed) != item.mechanism_hash:
            raise ValueError("MECHANISM_HASH_MISMATCH")
        return item


# ---------------------------------------------------------------------------
# MechanismLibrary
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MechanismLibrary:
    library_version: str
    candidates: tuple[MechanismCandidate, ...]

    @classmethod
    def create(cls, candidates: Iterable[MechanismCandidate]) -> "MechanismLibrary":
        ordered = tuple(sorted(candidates, key=lambda c: c.mechanism_id))
        ids = [c.mechanism_id for c in ordered]
        if len(ids) != len(set(ids)):
            raise ValueError("MECHANISM_ID_DUPLICATE")
        for candidate in ordered:
            candidate.validate()
        return cls(library_version=MECHANISM_LIBRARY_VERSION, candidates=ordered)

    def payload(self) -> dict[str, Any]:
        return {
            "library_version": self.library_version,
            "candidates": [c.as_dict() for c in self.candidates],
        }

    @property
    def library_hash(self) -> str:
        return canonical_hash(self.payload())

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "library_hash": self.library_hash}

    def verify(self) -> bool:
        for candidate in self.candidates:
            candidate.validate()
            if canonical_hash(candidate.payload()) != candidate.mechanism_hash:
                return False
        return canonical_hash(self.payload()) == self.library_hash

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MechanismLibrary":
        candidates = tuple(
            MechanismCandidate.from_dict(item) for item in value.get("candidates", ())
        )
        lib = cls(
            library_version=str(value.get("library_version", MECHANISM_LIBRARY_VERSION)),
            candidates=candidates,
        )
        claimed = value.get("library_hash")
        if claimed is not None and str(claimed) != lib.library_hash:
            raise ValueError("LIBRARY_HASH_MISMATCH")
        return lib

    # ------------------------------------------------------------------
    # Phase 9: Accumulation — load, add, save across runs
    # ------------------------------------------------------------------

    def add_candidate(self, candidate: MechanismCandidate) -> "MechanismLibrary":
        """Add a new mechanism candidate (idempotent on mechanism_id)."""
        if candidate.mechanism_id in {c.mechanism_id for c in self.candidates}:
            return self  # already in library
        new_candidates = tuple(sorted(self.candidates + (candidate,), key=lambda c: c.mechanism_id))
        return MechanismLibrary(library_version=self.library_version, candidates=new_candidates)

    @classmethod
    def load(cls, path: str | Path) -> "MechanismLibrary":
        """Load accumulated mechanism library from a file.
        Returns an empty library if the file doesn't exist (first run).
        """
        from pathlib import Path
        import json
        p = Path(path)
        if not p.is_file():
            return cls.create(())
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def save(self, path: str | Path) -> None:
        """Persist the accumulated mechanism library to a file."""
        from .util import write_json
        write_json(path, self.as_dict())

    # ------------------------------------------------------------------
    # Constitutional guard: only A3 may influence organization generation.
    # Slice 3 admits A0/A1 only, so the library must exert NO influence.
    # ------------------------------------------------------------------

    def has_a3_influence(self) -> bool:
        return any(
            MechanismState(c.status) is MechanismState.A3_ASSIMILATED
            for c in self.candidates
        )

    def assert_no_a3_influence(self) -> None:
        if self.has_a3_influence():
            raise ValueError("MECHANISM_LIBRARY_A3_INFLUENCE_FORBIDDEN_IN_SLICE3")
