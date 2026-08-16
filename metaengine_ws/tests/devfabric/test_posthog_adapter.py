import json
import pytest

from metaengine.devfabric.models import PrivacyClass, RiskClass, TaskEnvelope
from metaengine.devfabric.providers.external import ConnectorPolicyError
from metaengine.devfabric.providers.posthog import PostHogTelemetryAdapter
from metaengine.devfabric.telemetry_policy import ALLOWED_TELEMETRY_FIELDS


class FakePostHog:
    def __init__(self):
        self.events = []

    def capture_event(self, event, properties):
        self.events.append((event, dict(properties)))
        return {"remote_id": "evt-1"}


def make_task(objective, privacy=PrivacyClass.P1):
    return TaskEnvelope.create(
        source_checkpoint_id="cp001-SECRET-SOURCE",
        source_tree_hash="a" * 40,
        objective=objective,
        acceptance_tests=(f"must not leak {objective}",),
        allowed_paths=(f"private/{objective}.py",),
        forbidden_paths=(".env",),
        capabilities_required=("telemetry",),
        risk_class=RiskClass.NORMAL,
        privacy_class=privacy,
    )


def test_arbitrary_objective_and_source_strings_never_appear_in_telemetry():
    sentinels = [
        "ULTRA_PRIVATE_ALPHA_123",
        "password=hunter2",
        "sk-" + "proj-never-serialize-this",
        "日本語秘密設計",
    ]
    for sentinel in sentinels:
        transport = FakePostHog()
        adapter = PostHogTelemetryAdapter(transport)
        adapter.emit(
            make_task(sentinel),
            provider_class="local_ai",
            task_class="code_change",
            latency_ms=123,
            compute_estimate=42,
            result="PASS",
            test_delta=3,
            patch_size=99,
            verifier_verdict="PASS",
            promotion_outcome="NOT_PROPOSED",
            quota_state="LOCAL_FREE",
            fallback="none",
            write_intent="EMIT_TELEMETRY",
        )
        blob = json.dumps(transport.events, ensure_ascii=False, sort_keys=True)
        assert sentinel not in blob
        assert "cp001-SECRET-SOURCE" not in blob
        assert set(transport.events[0][1]) == ALLOWED_TELEMETRY_FIELDS


def test_p3_telemetry_is_blocked():
    adapter = PostHogTelemetryAdapter(FakePostHog())
    with pytest.raises(ConnectorPolicyError) as exc:
        adapter.emit(
            make_task("private", PrivacyClass.P3),
            provider_class="local_ai", task_class="code_change", latency_ms=1,
            compute_estimate=1, result="PASS", test_delta=0, patch_size=0,
            verifier_verdict="PASS", promotion_outcome="NONE",
            quota_state="LOCAL_FREE", fallback="none",
            write_intent="EMIT_TELEMETRY",
        )
    assert exc.value.reason_code == "PRIVACY_CLASS_BLOCKED"
