from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .models import TaskEnvelope
from .policy import privacy_allowed, zero_spend_allowed
from .providers.base import ProviderAdapter


@dataclass(frozen=True)
class DispatchDecision:
    selected: tuple[str, ...]
    rejected: tuple[str, ...]
    reasons: tuple[str, ...]


class DevFabricRouter:
    def __init__(self, *, max_parallel: int = 4, effectiveness_priors: Mapping[str, float] | None = None):
        if max_parallel < 1:
            raise ValueError("max_parallel must be >= 1")
        self.max_parallel = max_parallel
        self.effectiveness_priors = dict(effectiveness_priors or {})

    def route(self, task: TaskEnvelope, providers: Iterable[ProviderAdapter]) -> DispatchDecision:
        eligible: list[tuple[tuple[object, ...], str]] = []
        rejected: list[str] = []
        reasons: list[str] = []

        required = set(task.capabilities_required)
        for provider in providers:
            descriptor = provider.descriptor
            if not required.issubset(set(descriptor.capabilities)):
                rejected.append(descriptor.provider_id)
                reasons.append("CAPABILITY_MISMATCH")
                continue

            privacy_ok, reason = privacy_allowed(task, descriptor)
            if not privacy_ok:
                rejected.append(descriptor.provider_id)
                reasons.append(reason or "PRIVACY_CLASS_BLOCKED")
                continue

            health = provider.health_check()
            if not health.healthy:
                rejected.append(descriptor.provider_id)
                reasons.append("PROVIDER_UNHEALTHY")
                continue

            quota = provider.quota_snapshot()
            spend_ok, reason = zero_spend_allowed(task, descriptor, quota)
            if not spend_ok:
                rejected.append(descriptor.provider_id)
                reasons.append(reason or "ZERO_SPEND_BLOCKED")
                continue

            latency = health.latency_ms if health.latency_ms is not None else 10**9
            measured_effectiveness = self.effectiveness_priors.get(descriptor.provider_id, descriptor.effectiveness)
            rank = (
                0 if not descriptor.external else 1,
                -float(measured_effectiveness),
                latency,
                descriptor.independence_group,
                descriptor.provider_id,
            )
            eligible.append((rank, descriptor.provider_id))

        eligible.sort(key=lambda item: item[0])
        selected = tuple(provider_id for _, provider_id in eligible[: self.max_parallel])
        return DispatchDecision(
            selected=selected,
            rejected=tuple(sorted(set(rejected))),
            reasons=tuple(sorted(set(reasons))),
        )
