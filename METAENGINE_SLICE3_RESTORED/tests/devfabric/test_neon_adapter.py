import pytest

from metaengine.devfabric.models import PrivacyClass, RiskClass, TaskEnvelope
from metaengine.devfabric.providers.external import ConnectorPolicyError
from metaengine.devfabric.providers.neon import NeonSandboxAdapter


class FakeNeon:
    def __init__(self):
        self.branches = {}
        self.sql = []

    def create_branch(self, name, tags, ttl_minutes):
        branch_id = f"br-{len(self.branches)+1}"
        self.branches[branch_id] = {"name": name, "tags": dict(tags), "ttl_minutes": ttl_minutes}
        return {"branch_id": branch_id}

    def run_sql(self, branch_id, sql):
        assert branch_id in self.branches
        self.sql.append((branch_id, sql))
        return {"status": "PASS"}

    def delete_branch(self, branch_id):
        self.branches.pop(branch_id, None)
        return {"deleted": True}


def task(privacy=PrivacyClass.P1):
    return TaskEnvelope.create(
        source_checkpoint_id="cp001",
        source_tree_hash="a" * 40,
        objective="test migration",
        acceptance_tests=("migration passes",),
        allowed_paths=("migrations/",), forbidden_paths=(".env",),
        capabilities_required=("database_sandbox",), risk_class=RiskClass.HIGH,
        privacy_class=privacy,
    )


def test_retired_neon_is_disabled_by_default():
    adapter = NeonSandboxAdapter(FakeNeon())
    with pytest.raises(ConnectorPolicyError) as exc:
        adapter.create_sandbox(
            task(), candidate_hash="b"*64, ttl_minutes=30, data_policy="SCHEMA_ONLY",
            write_intent="CREATE_SANDBOX",
        )
    assert exc.value.reason_code == "NEON_RETIRED_BY_POLICY"


def test_p2_requires_schema_only_or_approved_synthetic_fixtures():
    adapter = NeonSandboxAdapter(FakeNeon(), enabled=True)
    with pytest.raises(ConnectorPolicyError) as exc:
        adapter.create_sandbox(
            task(PrivacyClass.P2), candidate_hash="b"*64, ttl_minutes=30,
            data_policy="COPY_CANONICAL_DATA", write_intent="CREATE_SANDBOX",
        )
    assert exc.value.reason_code == "SENSITIVE_DATA_POLICY_BLOCKED"


def test_p3_is_never_dispatched_to_neon():
    adapter = NeonSandboxAdapter(FakeNeon(), enabled=True)
    with pytest.raises(ConnectorPolicyError) as exc:
        adapter.create_sandbox(
            task(PrivacyClass.P3), candidate_hash="b"*64, ttl_minutes=30,
            data_policy="SCHEMA_ONLY", write_intent="CREATE_SANDBOX",
        )
    assert exc.value.reason_code == "PRIVACY_CLASS_BLOCKED"


def test_sandbox_is_tagged_bounded_and_cleanup_receipted():
    transport = FakeNeon()
    adapter = NeonSandboxAdapter(transport, enabled=True)
    handle, create_receipt = adapter.create_sandbox(
        task(), candidate_hash="b"*64, ttl_minutes=30, data_policy="SCHEMA_ONLY",
        write_intent="CREATE_SANDBOX",
    )
    assert create_receipt.status == "PASS"
    assert handle.ttl_minutes == 30
    meta = transport.branches[handle.branch_id]
    assert meta["tags"]["task_id"] == task().task_id
    assert meta["tags"]["candidate_hash"] == "b"*64
    adapter.run_migration_test(handle, "select 1")
    cleanup = adapter.destroy_sandbox(handle, write_intent="DESTROY_SANDBOX")
    assert cleanup.status == "PASS"
    assert handle.branch_id not in transport.branches


def test_canonical_role_execution_is_rejected():
    transport = FakeNeon()
    adapter = NeonSandboxAdapter(transport, enabled=True)
    handle, _ = adapter.create_sandbox(
        task(), candidate_hash="c"*64, ttl_minutes=10, data_policy="SCHEMA_ONLY",
        write_intent="CREATE_SANDBOX",
    )
    with pytest.raises(ConnectorPolicyError) as exc:
        adapter.run_migration_test(handle, "select 1", canonical_role=True)
    assert exc.value.reason_code == "CANONICAL_ROLE_FORBIDDEN"
