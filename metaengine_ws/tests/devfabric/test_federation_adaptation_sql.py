from __future__ import annotations

import re
from pathlib import Path


SQL_ROOT = Path(__file__).resolve().parents[2] / "storage"
SQL_PATHS = (
    SQL_ROOT / "federated_chat_fabric_d6_adaptation.sql",
    SQL_ROOT / "federated_chat_fabric_d6_adaptation_fix.sql",
)


def _sql() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in SQL_PATHS if path.exists()).lower()


def _function_block(name: str) -> str:
    sql = _sql()
    start = sql.rindex(f"create or replace function public.{name}")
    end = sql.index("$$;", start) + 3
    return sql[start:end]


def test_adaptation_migration_creates_append_only_receipt_table() -> None:
    sql = _sql()
    table = "destruktion_meta.federated_adaptation_receipt"
    assert f"create table {table}" in sql
    assert "adaptation_receipt_hash text primary key" in sql
    assert "adaptation_input_hash text not null unique" in sql
    assert f"alter table {table} enable row level security" in sql
    assert f"alter table {table} force row level security" in sql
    assert f"revoke all on table {table} from public, anon, authenticated" in sql
    assert f"revoke all on table {table} from service_role" in sql
    assert f"grant select, insert on table {table} to service_role" in sql
    assert f"revoke update, delete, truncate on table {table} from service_role" in sql
    assert "before update or delete on destruktion_meta.federated_adaptation_receipt" in sql
    assert "federation_adaptation_immutable" in sql


def test_adaptation_migration_hardens_existing_role_tables_and_never_materializes_shadow_profile() -> None:
    sql = _sql()
    assert "revoke update, delete, truncate on table destruktion_meta.federated_role_genome from service_role" in sql
    assert "revoke update, delete, truncate on table destruktion_meta.federated_role_outcome from service_role" in sql
    assert "insert into destruktion_meta.federated_role_genome" not in sql
    assert "update destruktion_meta.federated_role_genome" not in sql
    assert "delete from destruktion_meta.federated_role_genome" not in sql


def test_adaptation_rpcs_are_fixed_security_invoker_service_role_only() -> None:
    sql = _sql()
    assert "security definer" not in sql
    for rpc in (
        "metaengine_federation_record_adaptation_receipt_v1",
        "metaengine_federation_adaptation_receipt_get_v1",
    ):
        block = _function_block(rpc)
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


def test_record_rpc_validates_finalization_references_and_conflicting_repeat() -> None:
    block = _function_block("metaengine_federation_record_adaptation_receipt_v1")
    assert "federated_epoch_finalization" in block
    assert "federation_adaptation_finalized_evidence_required" in block
    assert "already_recorded" in block
    assert "federation_adaptation_nondeterministic" in block
    assert "pg_advisory_xact_lock" in block
    assert "for update" not in block
    assert "d6.adaptation.1" in block
