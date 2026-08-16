from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .util import canonical_hash


@dataclass(frozen=True)
class EvidenceRef:
    """A source-bound reference. Derived text is never valid primary evidence."""

    source_id: str
    start: int
    end: int
    text_hash: str
    kind: str = "ORIGINAL_SOURCE_SPAN"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TypedTransformation:
    transformation_type: str
    proposition: str
    source_spans: tuple[EvidenceRef, ...] = ()
    assumptions: tuple[str, ...] = ()
    rival_id: str | None = None
    falsifier: str | None = None
    residual_tensions: tuple[str, ...] = ()
    abstention_reason: str | None = None
    provenance: str = "ACTUAL_EXECUTOR_OUTPUT"
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["source_spans"] = [span.as_dict() for span in self.source_spans]
        row["type"] = row.pop("transformation_type")
        row["label"] = row["proposition"]
        return row


@dataclass(frozen=True)
class UsageTelemetry:
    wall_seconds: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    tool_calls: int = 0
    cost_usd: float | None = None
    provider_request_ids: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def contract_hash(value: dict[str, Any]) -> str:
    return canonical_hash(value)

