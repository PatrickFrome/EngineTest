from __future__ import annotations

import re
from pathlib import Path

import pytest


SQL_PATH = Path(__file__).resolve().parents[2] / "storage" / "federated_chat_fabric_d6.sql"

TABLES = (
    "federated_epoch",
    "federated_slot",
    "federated_role_genome",
    "federated_session",
    "federated_task",
    "federated_assignment",
    "federated_candidate_receipt",
    "federated_review_receipt",
    "federated_conflict_event",
    "federated_integration_decision",
    "federated_sync_snapshot",
    "federated_role_outcome",
)

READ_RPCS = (
    "metaengine_federation_status_v1",
    "metaengine_federation_slot_catalog_v1",
    "metaengine_federation_session_status_v1",
    "metaengine_federation_epoch_status_v1",
    "metaengine_federation_task_get_v1",
    "metaengine_federation_task_dependencies_v1",
    "metaengine_federation_candidate_status_v1",
    "metaengine_federation_conflict_status_v1",
    "metaengine_federation_sync_snapshot_get_v1",
)

WRITE_RPCS = (
    "metaengine_federation_register_v1",
    "metaengine_federation_release_v1",
    "metaengine_federation_claim_task_v1",
    "metaengine_federation_progress_v1",
    "metaengine_federation_submit_candidate_v1",
    "metaengine_federation_submit_review_v1",
    "metaengine_federation_submit_conflict_v1",
    "metaengine_federation_propose_integration_v1",
    "metaengine_federation_publish_snapshot_v1",
)

INTERNAL_RPCS = (
    "metaengine_federation_open_epoch_v1",
    "metaengine_federation_seed_task_v1",
    "metaengine_federation_seed_role_genome_v1",
    "metaengine_federation_reclaim_slot_v1",
)


def _sql() -> str:
    return SQL_PATH.read_text(encoding="utf-8").lower()


def test_migration_declares_all_private_tables_and_rls_guards() -> None:
    sql = _sql()
    assert "security definer" not in sql
    assert "grant execute" in sql
    for table in TABLES:
        qualified = f"destruktion_meta.{table}"
        assert f"create table if not exists {qualified}" in sql
        assert f"alter table {qualified} enable row level security" in sql
        assert f"alter table {qualified} force row level security" in sql
        assert re.search(
            rf"revoke\s+all\s+on\s+table\s+{re.escape(qualified)}\s+from\s+anon\s*,\s*authenticated",
            sql,
        )
        assert re.search(
            rf"grant\s+select\s*,\s*insert\s*,\s*update\s*,\s*delete\s+on\s+table\s+{re.escape(qualified)}\s+to\s+service_role",
            sql,
        )


def test_migration_exposes_only_fixed_service_role_rpc_surface() -> None:
    sql = _sql()
    for rpc in (*READ_RPCS, *WRITE_RPCS, *INTERNAL_RPCS):
        assert f"create or replace function public.{rpc}" in sql
        assert re.search(
            rf"revoke\s+all\s+on\s+function\s+public\.{rpc}\([^;]*?\)\s+from\s+public\s*,\s*anon\s*,\s*authenticated",
            sql,
            flags=re.S,
        )
        assert re.search(
            rf"grant\s+execute\s+on\s+function\s+public\.{rpc}\([^;]*?\)\s+to\s+service_role",
            sql,
            flags=re.S,
        )


def test_migration_never_grants_federation_objects_to_chat_roles() -> None:
    sql = _sql()
    forbidden = re.findall(
        r"grant\s+(?:select|insert|update|delete|execute|all)[^;]*\s+to\s+(anon|authenticated)\b",
        sql,
        flags=re.S,
    )
    assert forbidden == []


@pytest.mark.parametrize("rpc", WRITE_RPCS)
def test_write_rpcs_are_security_invoker_with_fixed_search_path(rpc: str) -> None:
    sql = _sql()
    start = sql.index(f"create or replace function public.{rpc}")
    end = sql.index("$$;", start) + 3
    body = sql[start:end]
    assert "security invoker" in body
    assert "set search_path = pg_catalog, destruktion_meta" in body

from metaengine.devfabric.federation.supabase_federation import SupabaseFederationAdapter
from metaengine.devfabric.federation.types import SlotId


class FakeRpcTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def call_rpc(self, rpc_name: str, params: dict[str, object]) -> object:
        self.calls.append((rpc_name, dict(params)))
        return {"rpc": rpc_name, "params": dict(params)}


def _h(char: str = "a") -> str:
    return char * 64


def test_adapter_has_no_generic_sql_or_rpc_surface() -> None:
    public = {name for name in dir(SupabaseFederationAdapter) if not name.startswith("_")}
    assert not any(token in name for name in public for token in ("sql", "execute", "query", "call_rpc"))
    assert "register" in public
    assert "open_epoch_internal" in public


def test_adapter_routes_fixed_read_and_write_calls() -> None:
    transport = FakeRpcTransport()
    adapter = SupabaseFederationAdapter(transport)
    adapter.status("epoch-1")
    adapter.register(
        epoch_id="epoch-1",
        requested_slot=SlotId.C2,
        session_id="session-1",
        capsule_sha256=_h("a"),
        protocol_version="D6.1",
        role_profile_hash=_h("b"),
    )
    adapter.submit_candidate(
        session_id="session-1",
        expected_generation=1,
        candidate_hash=_h("c"),
        task_hash=_h("d"),
        receipt={"candidate_hash": _h("c")},
    )
    assert [name for name, _ in transport.calls] == [
        "metaengine_federation_status_v1",
        "metaengine_federation_register_v1",
        "metaengine_federation_submit_candidate_v1",
    ]
    assert transport.calls[1][1]["p_requested_slot"] == "C2"


def test_adapter_validates_hashes_and_fixed_enums_before_transport() -> None:
    transport = FakeRpcTransport()
    adapter = SupabaseFederationAdapter(transport)
    with pytest.raises(ValueError, match="candidate_hash"):
        adapter.submit_candidate(
            session_id="session-1",
            expected_generation=1,
            candidate_hash="not-a-hash",
            task_hash=_h("d"),
            receipt={},
        )
    with pytest.raises(ValueError, match="decision"):
        adapter.propose_integration(
            session_id="sync-1",
            expected_generation=1,
            decision_hash=_h("e"),
            epoch_id="epoch-1",
            candidate_hash=_h("c"),
            decision="PROMOTE",
            reason="no",
        )
    assert transport.calls == []


def test_adapter_internal_control_plane_is_fixed_and_validated() -> None:
    transport = FakeRpcTransport()
    adapter = SupabaseFederationAdapter(transport)
    adapter.open_epoch_internal(
        epoch_id="epoch-1",
        base_checkpoint_id="cp-1",
        base_payload_root=_h("1"),
        federation_policy_hash=_h("2"),
        role_catalog_hash=_h("3"),
        producer_concurrency=4,
    )
    adapter.seed_role_genome_internal(
        role_profile_hash=_h("4"),
        slot_id=SlotId.C6,
        genome_version="D6.1-C6",
        parent_profile_hash=None,
        hard_genome={"slot": "C6"},
        soft_genome={"security": 0.9},
    )
    assert [name for name, _ in transport.calls] == [
        "metaengine_federation_open_epoch_v1",
        "metaengine_federation_seed_role_genome_v1",
    ]


def test_adapter_rejects_out_of_range_generation_and_concurrency() -> None:
    adapter = SupabaseFederationAdapter(FakeRpcTransport())
    with pytest.raises(ValueError, match="expected_generation"):
        adapter.release(session_id="s", expected_generation=-1)
    with pytest.raises(ValueError, match="producer_concurrency"):
        adapter.open_epoch_internal(
            epoch_id="epoch",
            base_checkpoint_id="cp",
            base_payload_root=_h("1"),
            federation_policy_hash=_h("2"),
            role_catalog_hash=_h("3"),
            producer_concurrency=7,
        )


def _function_block(name: str) -> str:
    sql = _sql()
    start = sql.index(f"create or replace function public.{name}")
    end = sql.index("$$;", start) + 3
    return sql[start:end]


def test_migration_never_mutates_canonical_checkpoint_or_champion() -> None:
    sql = _sql()
    assert "insert into destruktion_meta.chat_capsule_checkpoint" not in sql
    assert "update destruktion_meta.chat_capsule_checkpoint" not in sql
    assert "delete from destruktion_meta.chat_capsule_checkpoint" not in sql
    assert "champion" not in " ".join(READ_RPCS + WRITE_RPCS + INTERNAL_RPCS)
    assert "promote" not in " ".join(READ_RPCS + WRITE_RPCS + INTERNAL_RPCS)


def test_register_locks_slot_and_server_assigns_generation() -> None:
    block = _function_block("metaengine_federation_register_v1")
    assert "for update" in block
    assert "v_generation := v_generation + 1" in block
    assert "federation_role_slot_mismatch" in block
    assert "p_expected_generation" not in block


def test_candidate_eligibility_is_server_computed_and_fencing_aware() -> None:
    block = _function_block("metaengine_federation_submit_candidate_v1")
    signature = block.split("returns jsonb", 1)[0]
    assert "p_eligibility" not in signature
    assert "stale_fenced" in block
    assert "missing_review" in block
    assert "lease_generation" in block


def test_candidate_risk_reads_canonical_federated_task_envelope_shape() -> None:
    block = _function_block("metaengine_federation_submit_candidate_v1")
    assert "envelope -> 'base_task' ->> 'risk_class'" in block
    assert "coalesce(" in block


def test_integration_requires_c0_and_fresh_c6_for_high_risk() -> None:
    block = _function_block("metaengine_federation_propose_integration_v1")
    assert "v_session.slot_id <> 'c0'" in block
    assert "rs.slot_id = 'c6'" in block
    assert "federation_review_stale_or_missing" in block


def test_integration_risk_reads_canonical_federated_task_envelope_shape() -> None:
    block = _function_block("metaengine_federation_propose_integration_v1")
    assert "envelope -> 'base_task' ->> 'risk_class'" in block
    assert "coalesce(" in block


FEDERATION_FK_INDEXES = (
    "create index if not exists idx_fed_epoch_base_checkpoint on destruktion_meta.federated_epoch(base_checkpoint_id)",
    "create index if not exists idx_fed_role_parent on destruktion_meta.federated_role_genome(parent_profile_hash)",
    "create index if not exists idx_fed_session_slot on destruktion_meta.federated_session(slot_id)",
    "create index if not exists idx_fed_session_role on destruktion_meta.federated_session(role_profile_hash)",
    "create index if not exists idx_fed_task_epoch on destruktion_meta.federated_task(epoch_id)",
    "create index if not exists idx_fed_task_owner on destruktion_meta.federated_task(owner_slot)",
    "create index if not exists idx_fed_task_role on destruktion_meta.federated_task(role_profile_hash)",
    "create index if not exists idx_fed_task_checkpoint on destruktion_meta.federated_task(base_checkpoint_id)",
    "create index if not exists idx_fed_assignment_task on destruktion_meta.federated_assignment(task_hash)",
    "create index if not exists idx_fed_assignment_session on destruktion_meta.federated_assignment(session_id)",
    "create index if not exists idx_fed_candidate_task on destruktion_meta.federated_candidate_receipt(task_hash)",
    "create index if not exists idx_fed_candidate_session on destruktion_meta.federated_candidate_receipt(session_id)",
    "create index if not exists idx_fed_review_candidate on destruktion_meta.federated_review_receipt(candidate_hash)",
    "create index if not exists idx_fed_review_session on destruktion_meta.federated_review_receipt(session_id)",
    "create index if not exists idx_fed_conflict_epoch on destruktion_meta.federated_conflict_event(epoch_id)",
    "create index if not exists idx_fed_conflict_left on destruktion_meta.federated_conflict_event(left_candidate_hash)",
    "create index if not exists idx_fed_conflict_right on destruktion_meta.federated_conflict_event(right_candidate_hash)",
    "create index if not exists idx_fed_decision_epoch on destruktion_meta.federated_integration_decision(epoch_id)",
    "create index if not exists idx_fed_decision_candidate on destruktion_meta.federated_integration_decision(candidate_hash)",
    "create index if not exists idx_fed_snapshot_epoch on destruktion_meta.federated_sync_snapshot(epoch_id)",
    "create index if not exists idx_fed_outcome_epoch on destruktion_meta.federated_role_outcome(epoch_id)",
    "create index if not exists idx_fed_outcome_slot on destruktion_meta.federated_role_outcome(slot_id)",
    "create index if not exists idx_fed_outcome_role on destruktion_meta.federated_role_outcome(role_profile_hash)",
)


def test_migration_indexes_federation_foreign_keys_for_multi_chat_load() -> None:
    sql = _sql()
    missing = [index for index in FEDERATION_FK_INDEXES if index not in sql]
    assert missing == []

FINALIZATION_SQL_PATH = Path(__file__).resolve().parents[2] / "storage" / "federated_chat_fabric_d6_finalization.sql"


def _finalization_sql() -> str:
    return FINALIZATION_SQL_PATH.read_text(encoding="utf-8").lower()


def _finalization_function_block(name: str) -> str:
    sql = _finalization_sql()
    start = sql.index(f"create or replace function public.{name}")
    end = sql.index("$$;", start) + 3
    return sql[start:end]


def test_finalization_migration_declares_immutable_private_table_and_indexes() -> None:
    sql = _finalization_sql()
    assert "create table destruktion_meta.federated_epoch_finalization" in sql
    assert "grant select, insert on table destruktion_meta.federated_epoch_finalization to service_role" in sql
    assert "revoke update, delete on table destruktion_meta.federated_epoch_finalization from service_role" in sql
    assert "alter table destruktion_meta.federated_epoch_finalization enable row level security" in sql
    assert "alter table destruktion_meta.federated_epoch_finalization force row level security" in sql
    assert "idx_fed_finalization_snapshot" in sql
    assert "final_snapshot_hash" in sql
    assert "idx_fed_finalization_session" in sql
    assert "finalized_by_session_id" in sql
    assert "security definer" not in sql


def test_finalization_migration_exposes_only_two_internal_service_role_rpcs() -> None:
    sql = _finalization_sql()
    for rpc in (
        "metaengine_federation_finalize_epoch_v1",
        "metaengine_federation_finalization_get_v1",
    ):
        assert f"create or replace function public.{rpc}" in sql
        block = _finalization_function_block(rpc)
        assert "security invoker" in block
        assert "set search_path = pg_catalog, destruktion_meta" in block
        assert re.search(
            rf"revoke\s+all\s+on\s+function\s+public\.{rpc}\([^;]*?\)\s+from\s+public\s*,\s*anon\s*,\s*authenticated",
            sql,
            flags=re.S,
        )
        assert re.search(
            rf"grant\s+execute\s+on\s+function\s+public\.{rpc}\([^;]*?\)\s+to\s+service_role",
            sql,
            flags=re.S,
        )


def test_finalization_table_has_immutable_update_delete_trigger() -> None:
    sql = _finalization_sql()
    assert "before update or delete on destruktion_meta.federated_epoch_finalization" in sql
    assert "federation_finalization_immutable" in sql
    assert "raise exception 'federation_finalization_immutable'" in sql

FINALIZATION_MUTATING_RPCS = (
    "metaengine_federation_register_v1",
    "metaengine_federation_claim_task_v1",
    "metaengine_federation_progress_v1",
    "metaengine_federation_submit_candidate_v1",
    "metaengine_federation_submit_review_v1",
    "metaengine_federation_submit_conflict_v1",
    "metaengine_federation_propose_integration_v1",
    "metaengine_federation_publish_snapshot_v1",
    "metaengine_federation_seed_task_v1",
    "metaengine_federation_reclaim_slot_v1",
)


@pytest.mark.parametrize("rpc", FINALIZATION_MUTATING_RPCS)
def test_finalization_migration_freezes_epoch_targeting_mutations(rpc: str) -> None:
    block = _finalization_function_block(rpc)
    assert "federation_epoch_immutable" in block
    assert "closed" in block
    assert "aborted" in block


def test_finalization_migration_does_not_replace_non_epoch_local_role_seed_or_release() -> None:
    sql = _finalization_sql()
    assert "create or replace function public.metaengine_federation_seed_role_genome_v1" not in sql
    assert "create or replace function public.metaengine_federation_release_v1" not in sql


def test_adapter_routes_fixed_internal_finalization_calls_and_validates_before_transport() -> None:
    transport = FakeRpcTransport()
    adapter = SupabaseFederationAdapter(transport)
    cut = {"cut_version": "D6.FINALIZATION.1"}
    adapter.finalize_epoch_internal(
        session_id="c0-session",
        expected_generation=2,
        epoch_id="epoch-1",
        finalization_hash=_h("a"),
        final_snapshot_hash=_h("b"),
        recovery_cut_hash=_h("c"),
        recovery_cut=cut,
        protocol_version="D6.FINALIZATION.1",
    )
    adapter.finalization_get_internal("epoch-1")
    assert transport.calls[0] == (
        "metaengine_federation_finalize_epoch_v1",
        {
            "p_session_id": "c0-session",
            "p_expected_generation": 2,
            "p_epoch_id": "epoch-1",
            "p_finalization_hash": _h("a"),
            "p_final_snapshot_hash": _h("b"),
            "p_recovery_cut_hash": _h("c"),
            "p_recovery_cut": cut,
            "p_protocol_version": "D6.FINALIZATION.1",
        },
    )
    assert transport.calls[1] == (
        "metaengine_federation_finalization_get_v1", {"p_epoch_id": "epoch-1"}
    )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"expected_generation": -1}, "expected_generation"),
        ({"session_id": ""}, "session_id"),
        ({"epoch_id": ""}, "epoch_id"),
        ({"finalization_hash": "bad"}, "finalization_hash"),
        ({"final_snapshot_hash": "bad"}, "final_snapshot_hash"),
        ({"recovery_cut_hash": "bad"}, "recovery_cut_hash"),
        ({"protocol_version": "D6.FINALIZATION.999"}, "protocol_version"),
        ({"recovery_cut": []}, "mapping"),
    ],
)
def test_adapter_rejects_invalid_finalization_inputs_before_transport(kwargs, message) -> None:
    transport = FakeRpcTransport()
    adapter = SupabaseFederationAdapter(transport)
    params = {
        "session_id": "c0-session",
        "expected_generation": 2,
        "epoch_id": "epoch-1",
        "finalization_hash": _h("a"),
        "final_snapshot_hash": _h("b"),
        "recovery_cut_hash": _h("c"),
        "recovery_cut": {"cut_version": "D6.FINALIZATION.1"},
        "protocol_version": "D6.FINALIZATION.1",
    }
    params.update(kwargs)
    with pytest.raises((ValueError, TypeError), match=message):
        adapter.finalize_epoch_internal(**params)
    assert transport.calls == []


def test_adapter_routes_fixed_adaptation_receipt_calls() -> None:
    transport = FakeRpcTransport()
    adapter = SupabaseFederationAdapter(transport)
    adapter.record_adaptation_receipt_internal(
        adaptation_receipt_hash=_h("a"),
        adaptation_input_hash=_h("b"),
        protocol_version="D6.ADAPTATION.1",
        evidence_finalization_hashes=(_h("c"), _h("d")),
        evidence_metrics_hash=_h("e"),
        status="HOLD_INSUFFICIENT_EVIDENCE",
        receipt={"adaptation_receipt_hash": _h("a"), "adaptation_input_hash": _h("b")},
    )
    adapter.adaptation_receipt_get_internal(_h("b"))
    assert [name for name, _ in transport.calls] == [
        "metaengine_federation_record_adaptation_receipt_v1",
        "metaengine_federation_adaptation_receipt_get_v1",
    ]
    assert transport.calls[0][1]["p_evidence_finalization_hashes"] == [_h("c"), _h("d")]


def test_adapter_rejects_invalid_adaptation_receipt_before_transport() -> None:
    transport = FakeRpcTransport()
    adapter = SupabaseFederationAdapter(transport)
    with pytest.raises(ValueError, match="adaptation_receipt_hash"):
        adapter.record_adaptation_receipt_internal(
            adaptation_receipt_hash="bad",
            adaptation_input_hash=_h("b"),
            protocol_version="D6.ADAPTATION.1",
            evidence_finalization_hashes=(_h("c"),),
            evidence_metrics_hash=_h("e"),
            status="HOLD_INSUFFICIENT_EVIDENCE",
            receipt={},
        )
    with pytest.raises(ValueError, match="evidence_finalization_hashes"):
        adapter.record_adaptation_receipt_internal(
            adaptation_receipt_hash=_h("a"),
            adaptation_input_hash=_h("b"),
            protocol_version="D6.ADAPTATION.1",
            evidence_finalization_hashes=(),
            evidence_metrics_hash=_h("e"),
            status="HOLD_INSUFFICIENT_EVIDENCE",
            receipt={},
        )
    with pytest.raises(ValueError, match="status"):
        adapter.record_adaptation_receipt_internal(
            adaptation_receipt_hash=_h("a"),
            adaptation_input_hash=_h("b"),
            protocol_version="D6.ADAPTATION.1",
            evidence_finalization_hashes=(_h("c"),),
            evidence_metrics_hash=_h("e"),
            status="PROMOTE",
            receipt={},
        )
    assert transport.calls == []
