from pathlib import Path

import pytest

from metaengine.devfabric.models import PrivacyClass, RiskClass, TaskEnvelope
from metaengine.devfabric.providers.external import ConnectorPolicyError
from metaengine.devfabric.providers.replit import ReplitWorkerAdapter
from metaengine.devfabric.router import DevFabricRouter


class FakeReplit:
    def __init__(self, *, quota_known, free_remaining, healthy=True):
        self.quota_known = quota_known
        self.free_remaining = free_remaining
        self.healthy = healthy
        self.payloads = []

    def health(self):
        return {"healthy": self.healthy, "detail": "fake"}

    def quota(self):
        return {
            "known": self.quota_known,
            "free_remaining": self.free_remaining,
            "paid_fallback_enabled": False,
        }

    def execute_task(self, payload):
        self.payloads.append(dict(payload))
        return {
            "base_tree_hash": "a" * 40,
            "patch_hash": "b" * 64,
            "changed_paths": ["metaengine/x.py"],
            "report_hash": "c" * 64,
        }


def task(privacy=PrivacyClass.P1):
    return TaskEnvelope.create(
        source_checkpoint_id="cp001",
        source_tree_hash="a" * 40,
        objective="Implement bounded worker",
        acceptance_tests=("tests pass",),
        allowed_paths=("metaengine/",), forbidden_paths=(".env",),
        capabilities_required=("CODE_GENERATOR",), risk_class=RiskClass.NORMAL,
        privacy_class=privacy,
    )


def test_unknown_free_credit_state_is_ineligible_under_zero_spend():
    provider = ReplitWorkerAdapter(FakeReplit(quota_known=False, free_remaining=None))
    decision = DevFabricRouter().route(task(), [provider])
    assert decision.selected == ()
    assert "ZERO_SPEND_QUOTA_UNKNOWN" in decision.reasons


def test_known_free_quota_can_be_selected_and_returns_candidate_receipt(tmp_path: Path):
    transport = FakeReplit(quota_known=True, free_remaining=5)
    provider = ReplitWorkerAdapter(transport)
    decision = DevFabricRouter().route(task(), [provider])
    assert decision.selected == (provider.descriptor.provider_id,)
    receipt = provider.execute(task(), tmp_path)
    assert receipt.provider_id == provider.descriptor.provider_id
    assert receipt.patch_hash == "b" * 64
    assert dict(receipt.metadata)["report_hash"] == "c" * 64
    blob = repr(transport.payloads[0])
    assert "SUPABASE" not in blob.upper()
    assert "SERVICE_ROLE" not in blob.upper()


def test_replit_is_bounded_to_p0_p1():
    provider = ReplitWorkerAdapter(FakeReplit(quota_known=True, free_remaining=10))
    with pytest.raises(ConnectorPolicyError) as exc:
        provider.execute(task(PrivacyClass.P2), Path("."))
    assert exc.value.reason_code == "PRIVACY_CLASS_BLOCKED"
