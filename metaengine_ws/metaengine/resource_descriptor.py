from __future__ import annotations

import string
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from .util import canonical_hash


RESOURCE_DESCRIPTOR_VERSION = "METAENGINE-RESOURCE-DESCRIPTOR-1"


class ResourceKind(str, Enum):
    MODEL = "MODEL"
    DETERMINISTIC_WORKER = "DETERMINISTIC_WORKER"
    VERIFIER = "VERIFIER"
    SEARCH = "SEARCH"
    HUMAN = "HUMAN"
    REMOTE_AGENT = "REMOTE_AGENT"
    LEGACY_ENGINE = "LEGACY_ENGINE"


class ObservationStatus(str, Enum):
    OBSERVED = "OBSERVED"
    UNOBSERVED = "UNOBSERVED"


class DeterminismClass(str, Enum):
    DETERMINISTIC = "DETERMINISTIC"
    SEEDED_STOCHASTIC = "SEEDED_STOCHASTIC"
    STOCHASTIC = "STOCHASTIC"
    UNKNOWN = "UNKNOWN"


class ResourceSecurityClass(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


def _is_hex(value: str, length: int) -> bool:
    return len(value) == length and all(ch in string.hexdigits for ch in value)


def _text(value: object, code: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(code)
    return result


def _strings(values: Iterable[object], *, code: str) -> tuple[str, ...]:
    normalized = tuple(sorted({_text(value, code) for value in values}))
    return normalized


def _pairs(values: Iterable[tuple[object, object]]) -> tuple[tuple[str, str], ...]:
    result: dict[str, str] = {}
    for key, value in values:
        k = _text(key, "RESOURCE_CONTEXT_KEY_REQUIRED")
        v = _text(value, "RESOURCE_CONTEXT_VALUE_REQUIRED")
        if k in result and result[k] != v:
            raise ValueError("RESOURCE_CONTEXT_DUPLICATE_KEY")
        result[k] = v
    return tuple(sorted(result.items()))


@dataclass(frozen=True)
class EvidenceBoundObservation:
    status: ObservationStatus
    value: str | int | float | bool | None
    unit: str | None
    evidence_hashes: tuple[str, ...]

    @classmethod
    def unobserved(cls) -> "EvidenceBoundObservation":
        return cls(ObservationStatus.UNOBSERVED, None, None, ())

    @classmethod
    def observed(
        cls,
        *,
        value: str | int | float | bool,
        unit: str | None,
        evidence_hashes: Iterable[str],
    ) -> "EvidenceBoundObservation":
        item = cls(
            ObservationStatus.OBSERVED,
            value,
            str(unit).strip() if unit is not None else None,
            tuple(sorted(set(str(x) for x in evidence_hashes))),
        )
        item.validate()
        return item

    def validate(self) -> None:
        status = ObservationStatus(self.status)
        if status is ObservationStatus.UNOBSERVED:
            if self.value is not None:
                raise ValueError("RESOURCE_OBSERVATION_UNOBSERVED_HAS_VALUE")
            if self.unit is not None:
                raise ValueError("RESOURCE_OBSERVATION_UNOBSERVED_HAS_UNIT")
            if self.evidence_hashes:
                raise ValueError("RESOURCE_OBSERVATION_UNOBSERVED_HAS_EVIDENCE")
            return
        if self.value is None:
            raise ValueError("RESOURCE_OBSERVATION_VALUE_REQUIRED")
        if not self.evidence_hashes:
            raise ValueError("RESOURCE_OBSERVATION_EVIDENCE_REQUIRED")
        if any(not _is_hex(value, 64) for value in self.evidence_hashes):
            raise ValueError("RESOURCE_OBSERVATION_EVIDENCE_HASH_INVALID")
        if self.unit is not None and not self.unit.strip():
            raise ValueError("RESOURCE_OBSERVATION_UNIT_INVALID")

    def payload(self) -> dict[str, Any]:
        self.validate()
        return {
            "status": ObservationStatus(self.status).value,
            "value": self.value,
            "unit": self.unit,
            "evidence_hashes": list(self.evidence_hashes),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvidenceBoundObservation":
        item = cls(
            status=ObservationStatus(str(value["status"])),
            value=value.get("value"),
            unit=value.get("unit"),
            evidence_hashes=tuple(str(x) for x in value.get("evidence_hashes", ())),
        )
        item.validate()
        return item


@dataclass(frozen=True)
class ResourceDescriptor:
    constitution_hash: str
    resource_id: str
    resource_kind: ResourceKind
    runtime_identity: str
    capabilities: tuple[str, ...]
    context_characteristics: tuple[tuple[str, str], ...]
    tool_capabilities: tuple[str, ...]
    input_modes: tuple[str, ...]
    output_modes: tuple[str, ...]
    determinism_class: DeterminismClass
    security_class: ResourceSecurityClass
    adapter_ref: str
    cost: EvidenceBoundObservation
    latency: EvidenceBoundObservation
    reliability: EvidenceBoundObservation

    @classmethod
    def create(
        cls,
        *,
        constitution_hash: str,
        resource_id: str,
        resource_kind: ResourceKind,
        runtime_identity: str,
        capabilities: Iterable[str],
        context_characteristics: Iterable[tuple[str, str]] = (),
        tool_capabilities: Iterable[str] = (),
        input_modes: Iterable[str] = (),
        output_modes: Iterable[str] = (),
        determinism_class: DeterminismClass = DeterminismClass.UNKNOWN,
        security_class: ResourceSecurityClass = ResourceSecurityClass.P0,
        adapter_ref: str,
        cost: EvidenceBoundObservation | None = None,
        latency: EvidenceBoundObservation | None = None,
        reliability: EvidenceBoundObservation | None = None,
    ) -> "ResourceDescriptor":
        item = cls(
            constitution_hash=str(constitution_hash),
            resource_id=_text(resource_id, "RESOURCE_ID_REQUIRED"),
            resource_kind=ResourceKind(resource_kind),
            runtime_identity=_text(runtime_identity, "RESOURCE_RUNTIME_IDENTITY_REQUIRED"),
            capabilities=_strings(capabilities, code="RESOURCE_CAPABILITY_ID_REQUIRED"),
            context_characteristics=_pairs(context_characteristics),
            tool_capabilities=_strings(tool_capabilities, code="RESOURCE_TOOL_CAPABILITY_ID_REQUIRED"),
            input_modes=_strings(input_modes, code="RESOURCE_INPUT_MODE_REQUIRED"),
            output_modes=_strings(output_modes, code="RESOURCE_OUTPUT_MODE_REQUIRED"),
            determinism_class=DeterminismClass(determinism_class),
            security_class=ResourceSecurityClass(security_class),
            adapter_ref=_text(adapter_ref, "RESOURCE_ADAPTER_REF_REQUIRED"),
            cost=cost or EvidenceBoundObservation.unobserved(),
            latency=latency or EvidenceBoundObservation.unobserved(),
            reliability=reliability or EvidenceBoundObservation.unobserved(),
        )
        item.validate()
        return item

    def validate(self) -> None:
        if not _is_hex(self.constitution_hash, 64):
            raise ValueError("RESOURCE_CONSTITUTION_HASH_INVALID")
        _text(self.resource_id, "RESOURCE_ID_REQUIRED")
        _text(self.runtime_identity, "RESOURCE_RUNTIME_IDENTITY_REQUIRED")
        _text(self.adapter_ref, "RESOURCE_ADAPTER_REF_REQUIRED")
        if not self.capabilities:
            raise ValueError("RESOURCE_CAPABILITIES_REQUIRED")
        for observation in (self.cost, self.latency, self.reliability):
            observation.validate()

    def payload(self) -> dict[str, Any]:
        self.validate()
        return {
            "descriptor_version": RESOURCE_DESCRIPTOR_VERSION,
            "constitution_hash": self.constitution_hash,
            "resource_id": self.resource_id,
            "resource_kind": self.resource_kind.value,
            "runtime_identity": self.runtime_identity,
            "capabilities": list(self.capabilities),
            "context_characteristics": [list(item) for item in self.context_characteristics],
            "tool_capabilities": list(self.tool_capabilities),
            "input_modes": list(self.input_modes),
            "output_modes": list(self.output_modes),
            "determinism_class": self.determinism_class.value,
            "security_class": self.security_class.value,
            "adapter_ref": self.adapter_ref,
            "cost": self.cost.payload(),
            "latency": self.latency.payload(),
            "reliability": self.reliability.payload(),
        }

    @property
    def descriptor_hash(self) -> str:
        return canonical_hash(self.payload())

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "descriptor_hash": self.descriptor_hash}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ResourceDescriptor":
        claimed = value.get("descriptor_hash")
        descriptor = cls.create(
            constitution_hash=str(value["constitution_hash"]),
            resource_id=str(value["resource_id"]),
            resource_kind=ResourceKind(str(value["resource_kind"])),
            runtime_identity=str(value["runtime_identity"]),
            capabilities=tuple(value.get("capabilities", ())),
            context_characteristics=tuple(tuple(x) for x in value.get("context_characteristics", ())),
            tool_capabilities=tuple(value.get("tool_capabilities", ())),
            input_modes=tuple(value.get("input_modes", ())),
            output_modes=tuple(value.get("output_modes", ())),
            determinism_class=DeterminismClass(str(value["determinism_class"])),
            security_class=ResourceSecurityClass(str(value["security_class"])),
            adapter_ref=str(value["adapter_ref"]),
            cost=EvidenceBoundObservation.from_dict(value.get("cost", {"status": "UNOBSERVED"})),
            latency=EvidenceBoundObservation.from_dict(value.get("latency", {"status": "UNOBSERVED"})),
            reliability=EvidenceBoundObservation.from_dict(value.get("reliability", {"status": "UNOBSERVED"})),
        )
        if claimed is not None and str(claimed) != descriptor.descriptor_hash:
            raise ValueError("RESOURCE_DESCRIPTOR_HASH_MISMATCH")
        return descriptor
