from pathlib import Path

from metaengine.devfabric.models import PrivacyClass, RiskClass, TaskEnvelope
from metaengine.devfabric.providers.base import (
    HealthSnapshot,
    ProviderDescriptor,
    QuotaSnapshot,
)
from metaengine.devfabric.router import DevFabricRouter


class FakeProvider:
    def __init__(self, descriptor, quota, health=None):
        self.descriptor = descriptor
        self._quota = quota
        self._health = health or HealthSnapshot(healthy=True, latency_ms=10)

    def health_check(self):
        return self._health

    def quota_snapshot(self):
        return self._quota

    def execute(self, task, workdir: Path):
        raise AssertionError("router tests must not execute providers")

    def cancel(self, task_id: str):
        return True


def task_factory(**overrides):
    values = dict(
        source_checkpoint_id="cp001",
        source_tree_hash="a" * 64,
        objective="code",
        acceptance_tests=("pytest -q",),
        allowed_paths=("metaengine/", "tests/"),
        forbidden_paths=("lineages/",),
        capabilities_required=("CODE_GENERATOR",),
        risk_class=RiskClass.NORMAL,
        privacy_class=PrivacyClass.P1,
    )
    values.update(overrides)
    return TaskEnvelope.create(**values)


def test_p3_never_routes_external():
    provider = FakeProvider(
        ProviderDescriptor(
            provider_id="external-free",
            capabilities=("CODE_GENERATOR",),
            external=True,
            billing_mode="FREE_ONLY",
        ),
        QuotaSnapshot(known=True, free_remaining=10, paid_fallback_enabled=False),
    )
    decision = DevFabricRouter().route(task_factory(privacy_class=PrivacyClass.P3), [provider])
    assert decision.selected == ()
    assert "PRIVACY_CLASS_BLOCKED" in decision.reasons


def test_unknown_paid_quota_fails_closed():
    provider = FakeProvider(
        ProviderDescriptor(
            provider_id="paid-capable",
            capabilities=("CODE_GENERATOR",),
            external=True,
            billing_mode="PAID_CAPABLE",
        ),
        QuotaSnapshot(known=False, free_remaining=None, paid_fallback_enabled=False),
    )
    decision = DevFabricRouter().route(task_factory(), [provider])
    assert decision.selected == ()
    assert "ZERO_SPEND_QUOTA_UNKNOWN" in decision.reasons


def test_equal_candidates_use_provider_id_as_stable_tie_breaker():
    def p(name):
        return FakeProvider(
            ProviderDescriptor(
                provider_id=name,
                capabilities=("CODE_GENERATOR",),
                external=False,
                billing_mode="LOCAL_FREE",
            ),
            QuotaSnapshot(known=True, free_remaining=None, paid_fallback_enabled=False),
        )

    decision = DevFabricRouter(max_parallel=2).route(task_factory(), [p("zeta"), p("alpha")])
    assert decision.selected == ("alpha", "zeta")
