import pytest

from metaengine.devfabric.providers.external import ConnectorPolicyError
from metaengine.devfabric.providers.supabase import SupabaseCanonicalAdapter


class FakeTransport:
    def __init__(self):
        self.current = {"checkpoint_id": "cp001", "payload_root_sha256": "a" * 64}
        self.champion = {"policy_hash": "b" * 64, "generation": 2}
        self.receipts = []
        self.proposals = []

    def read_current_checkpoint(self):
        return dict(self.current)

    def read_champion(self):
        return dict(self.champion)

    def append_development_receipt(self, payload):
        self.receipts.append(dict(payload))
        return {"remote_id": "receipt-1"}

    def propose_checkpoint(self, payload, expected_parent):
        if expected_parent != self.current["checkpoint_id"]:
            return {"applied": False, "reason_code": "CAS_CONFLICT"}
        self.proposals.append(dict(payload))
        return {"applied": True, "remote_id": payload["checkpoint_id"]}


def test_read_only_adapter_reads_checkpoint_and_champion():
    adapter = SupabaseCanonicalAdapter(FakeTransport(), read_only=True)
    assert adapter.read_current_checkpoint()["checkpoint_id"] == "cp001"
    assert adapter.read_champion()["generation"] == 2


def test_read_only_adapter_rejects_writes():
    adapter = SupabaseCanonicalAdapter(FakeTransport(), read_only=True)
    with pytest.raises(ConnectorPolicyError) as exc:
        adapter.append_development_receipt(
            {"event_hash": "c" * 64}, write_intent="APPEND_RECEIPT"
        )
    assert exc.value.reason_code == "CONNECTOR_READ_ONLY"


def test_append_requires_exact_write_intent():
    adapter = SupabaseCanonicalAdapter(FakeTransport(), read_only=False)
    with pytest.raises(ConnectorPolicyError) as exc:
        adapter.append_development_receipt({"event_hash": "c" * 64}, write_intent=None)
    assert exc.value.reason_code == "WRITE_INTENT_REQUIRED"


def test_wrong_parent_returns_cas_conflict_without_creating_proposal():
    transport = FakeTransport()
    adapter = SupabaseCanonicalAdapter(transport, read_only=False)
    receipt = adapter.propose_checkpoint(
        {
            "checkpoint_id": "cp002-dev",
            "payload_root_sha256": "d" * 64,
            "capsule_sha256": "e" * 64,
        },
        expected_parent="wrong-parent",
        write_intent="PROPOSE_CHECKPOINT",
    )
    assert receipt.status == "REJECTED"
    assert receipt.reason_code == "CAS_CONFLICT"
    assert transport.proposals == []


def test_correct_parent_creates_non_promoting_checkpoint_proposal():
    transport = FakeTransport()
    adapter = SupabaseCanonicalAdapter(transport, read_only=False)
    receipt = adapter.propose_checkpoint(
        {
            "checkpoint_id": "cp002-dev",
            "payload_root_sha256": "d" * 64,
            "capsule_sha256": "e" * 64,
            "is_current": False,
            "verification_status": "NON_CANONICAL",
        },
        expected_parent="cp001",
        write_intent="PROPOSE_CHECKPOINT",
    )
    assert receipt.status == "PASS"
    assert receipt.remote_id == "cp002-dev"
    assert transport.proposals[0]["parent_checkpoint_id"] == "cp001"
    assert transport.proposals[0]["is_current"] is False
    assert transport.proposals[0]["verification_status"] == "NON_CANONICAL"


def test_adapter_has_no_arbitrary_sql_or_promote_shortcuts():
    public = {name for name in dir(SupabaseCanonicalAdapter) if not name.startswith("_")}
    assert "execute_sql" not in public
    assert "run_sql" not in public
    assert "promote" not in public
    assert "set_current" not in public
