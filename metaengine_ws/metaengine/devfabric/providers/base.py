from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..models import CandidateReceipt, TaskEnvelope


@dataclass(frozen=True)
class ProviderDescriptor:
    provider_id: str
    capabilities: tuple[str, ...]
    external: bool
    billing_mode: str
    effectiveness: float = 0.0
    independence_group: str = "default"


@dataclass(frozen=True)
class HealthSnapshot:
    healthy: bool
    latency_ms: int | None = None
    detail: str = ""


@dataclass(frozen=True)
class QuotaSnapshot:
    known: bool
    free_remaining: int | None
    paid_fallback_enabled: bool
    detail: str = ""


class ProviderAdapter(Protocol):
    descriptor: ProviderDescriptor

    def health_check(self) -> HealthSnapshot: ...
    def quota_snapshot(self) -> QuotaSnapshot: ...
    def execute(self, task: TaskEnvelope, workdir: Path) -> CandidateReceipt: ...
    def cancel(self, task_id: str) -> bool: ...
