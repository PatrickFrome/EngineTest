from __future__ import annotations

import json
import tomllib
from pathlib import Path, PurePosixPath

from metaengine.devfabric.capsule import _excluded, make_gate_receipt, verify_gate_receipt

ROOT = Path(__file__).resolve().parents[2]


def test_stage_d6_gate_receipt_uses_distinct_version_and_stays_external(tmp_path: Path) -> None:
    assert _excluded(PurePosixPath("devfabric/artifacts/manifests/stage-d6-gate.json"))
    receipt = make_gate_receipt(
        {
            "stage": "D6-F",
            "development_status": "PASS",
            "certification_status": "BLOCKED_EXTERNAL_NODE_TOOLCHAIN",
        },
        gate_version="METAENGINE-DEVFABRIC-STAGE-D6-GATE-1",
    )
    path = tmp_path / "stage-d6-gate.json"
    path.write_text(json.dumps(receipt, sort_keys=True))
    verified = verify_gate_receipt(path)
    assert verified["status"] == "PASS"
    assert verified["gate_version"] == "METAENGINE-DEVFABRIC-STAGE-D6-GATE-1"


def test_federation_verifier_profile_covers_pilot_edge_devfabric_and_engine() -> None:
    data = tomllib.loads((ROOT / "devfabric" / "verification" / "profiles.toml").read_text())
    commands = data["profiles"]["federation"]["commands"]
    joined = "\n".join(commands)
    assert "test_federation_pilot.py" in joined
    assert "test_federation_contracts.py" in joined
    assert "devfabric/cloudflare/test" in joined
    assert "federation_contract.test.ts" in joined
    assert "federation_tools.test.ts" in joined
    assert "tsconfig.core.json" in joined
    assert "tests/devfabric" in joined
    assert "--ignore=tests/devfabric" in joined
    assert "uv run --locked" not in joined
    assert "npm install" not in joined
    assert "metaengine.devfabric.isolated_suite_runner tests/devfabric" in joined


def test_controlled_machine_epoch_is_deterministic_and_recovers_c0(tmp_path: Path) -> None:
    from metaengine.devfabric.federation.pilot import run_controlled_epoch
    from metaengine.devfabric.federation.store import FederationStore

    checkpoint = "metaengine-chat-2.3.0-alpha.1-cp001"
    payload_root = "37ec1f81a2f1ef6ea0aed90582cc177f44fc3cca563d782fd7cc780575f94e1d"
    reports = []
    for index in range(2):
        store = FederationStore(tmp_path / f"pilot-{index}.sqlite3")
        try:
            reports.append(run_controlled_epoch(store, checkpoint, payload_root))
        finally:
            store.close()

    first, second = reports
    assert first.status == "PASS"
    assert first.snapshot_hash == first.recovered_snapshot_hash
    assert first.snapshot_hash == second.snapshot_hash
    assert first.integration_order == second.integration_order
    assert first.integration_order
    assert first.stale_candidate_hash in first.stale_candidates
    assert first.replacement_slot == "C3"
    assert first.replacement_generation == 2
    assert first.c0_recovered is True
    assert {item.slot_id for item in first.registrations} == {"C0", "C2", "C3", "C4", "C6", "C7"}
    assert any(ref.startswith("INTERFACE_CONTRACT_CONFLICT:") for ref in first.conflict_refs)
    assert first.conflict_task_ref.startswith("conflict-task-")
    assert first.review_hash
    assert first.c2_candidate_hash in first.eligible_candidates
    assert first.c2_candidate_hash not in first.integration_order


def test_machine_epoch_records_high_risk_c6_review_and_stale_fencing(tmp_path: Path) -> None:
    from metaengine.devfabric.federation.pilot import run_controlled_epoch
    from metaengine.devfabric.federation.store import FederationStore

    store = FederationStore(tmp_path / "pilot.sqlite3")
    try:
        report = run_controlled_epoch(
            store,
            "metaengine-chat-2.3.0-alpha.1-cp001",
            "37ec1f81a2f1ef6ea0aed90582cc177f44fc3cca563d782fd7cc780575f94e1d",
        )
        assert store.get_session(report.old_c3_session_id)["released_at"] == "RELEASED"
        assert store.get_session(report.new_c3_session_id)["lease_generation"] == 2
        stale = store.candidate_row(report.stale_candidate_hash)
        assert stale is not None and stale["eligibility"] == "STALE_FENCED"
        reviews = store.list_review_rows(report.c2_candidate_hash)
        assert len(reviews) == 1
        assert reviews[0]["review_hash"] == report.review_hash
        assert store.latest_snapshot_row(report.epoch_id) is not None
    finally:
        store.close()


def test_one_capsule_generates_eight_secret_free_connected_role_packets() -> None:
    from metaengine.devfabric.federation.bootstrap import connected_role_packets, load_bootstrap

    context = load_bootstrap(ROOT)
    packets = connected_role_packets(context)
    assert len(packets) == 8
    assert tuple(packet["slot_id"] for packet in packets) == tuple(f"C{i}" for i in range(8))
    assert len({packet["role_profile_hash"] for packet in packets}) == 8
    assert {packet["capsule_reference"]["source_artifact_sha256"] for packet in packets} == {
        context.source_artifact_sha256
    }
    for packet in packets:
        assert packet["capsule_reference"]["mode"] == "ONE_COMMON_CONTROL_CAPSULE"
        assert packet["multi_chat_ui_status"] == "READY_FOR_CANARY_NOT_OBSERVED"
        assert "session_id" not in packet
        assert "epoch_id" not in packet
        assert "lease_generation" not in packet
        register = packet["tool_sequence"][0]
        assert register["tool"] == "federation_register"
        assert register["arguments"]["requested_slot"] == packet["slot_id"]
        assert register["arguments"]["role_profile_hash"] == packet["role_profile_hash"]
        assert register["arguments"]["epoch_id"] == "<ACTIVE_EPOCH_ID>"
        assert register["arguments"]["capsule_sha256"] == "<CONTROL_CAPSULE_SHA256>"
        assert any(step["tool"] == "task_get" for step in packet["tool_sequence"])
        serialized = json.dumps(packet, sort_keys=True).lower()
        assert "service_role" not in serialized
        assert "password" not in serialized
        assert "credential" not in serialized


def test_real_chat_pilot_runbook_is_four_chat_canary_and_does_not_claim_observed_pass() -> None:
    runbook = (ROOT / "chat_federation" / "PILOT_RUNBOOK.md").read_text(encoding="utf-8")
    template = (ROOT / "chat_federation" / "ROLE_BOOTSTRAP_TEMPLATE.md").read_text(encoding="utf-8")
    for slot in ("C0", "C2", "C4", "C6"):
        assert slot in runbook
    assert "READY_FOR_CANARY_NOT_OBSERVED" in runbook
    assert "PASS_CANARY" in runbook
    assert "user opens" in runbook.lower()
    assert "same CONTROL capsule" in runbook
    assert "federation_register" in template
    assert "task_get" in template
    assert "Project memory" in template
    assert "machine truth" in template


def test_stage_d6_g0_gate_receipt_uses_distinct_version_and_stays_external(tmp_path: Path) -> None:
    assert _excluded(PurePosixPath("devfabric/artifacts/manifests/stage-d6-g0-gate.json"))
    receipt = make_gate_receipt(
        {
            "stage": "D6-G0",
            "development_status": "PASS",
            "certification_status": "BLOCKED_EXTERNAL_NODE_TOOLCHAIN",
        },
        gate_version="METAENGINE-DEVFABRIC-STAGE-D6-G0-GATE-1",
    )
    path = tmp_path / "stage-d6-g0-gate.json"
    path.write_text(json.dumps(receipt, sort_keys=True))
    verified = verify_gate_receipt(path)
    assert verified["status"] == "PASS"
    assert verified["gate_version"] == "METAENGINE-DEVFABRIC-STAGE-D6-G0-GATE-1"


def test_finalization_verifier_profile_has_exact_observable_commands() -> None:
    data = tomllib.loads((ROOT / "devfabric" / "verification" / "profiles.toml").read_text())
    assert data["profiles"]["federation-finalization"]["commands"] == [
        "python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_finalization.py tests/devfabric/test_federation_synchronizer.py tests/devfabric/test_federation_simulator.py tests/devfabric/test_federation_supabase_adapter.py tests/devfabric/test_federation_pilot.py",
        "node --experimental-strip-types --test devfabric/cloudflare/test/federation_contract.test.ts devfabric/cloudflare/test/federation_tools.test.ts",
        "tsc --noEmit -p devfabric/cloudflare/tsconfig.core.json",
        "python -m metaengine.devfabric.isolated_suite_runner tests/devfabric --timeout-seconds 180",
        "python -m metaengine.devfabric.pytest_runner -q tests --ignore=tests/devfabric",
    ]



def test_stage_d6_g1_gate_receipt_uses_distinct_version_and_stays_external(tmp_path: Path) -> None:
    assert _excluded(PurePosixPath("devfabric/artifacts/manifests/stage-d6-g1-gate.json"))
    receipt = make_gate_receipt(
        {
            "stage": "D6-G1",
            "development_status": "PASS_ADAPTATION_SHADOW_READY",
            "original_source_head_provenance": "71d36a12e5b810431739fc5d9b111fa4ffb955f5",
            "reconstructed_git_root": "0a0cb3eb38205121d4cf091c14ca2591744f0aed",
        },
        gate_version="METAENGINE-DEVFABRIC-STAGE-D6-G1-GATE-1",
    )
    path = tmp_path / "stage-d6-g1-gate.json"
    path.write_text(json.dumps(receipt, sort_keys=True))
    verified = verify_gate_receipt(path)
    assert verified["status"] == "PASS"
    assert verified["gate_version"] == "METAENGINE-DEVFABRIC-STAGE-D6-G1-GATE-1"


def test_adaptation_verifier_profile_has_exact_observable_commands() -> None:
    data = tomllib.loads((ROOT / "devfabric" / "verification" / "profiles.toml").read_text())
    assert data["profiles"]["federation-adaptation"]["commands"] == [
        "python -m metaengine.devfabric.pytest_runner -q tests/devfabric/test_federation_adaptation.py tests/devfabric/test_federation_telemetry.py tests/devfabric/test_federation_adaptation_sql.py tests/devfabric/test_federation_finalization.py tests/devfabric/test_federation_supabase_adapter.py tests/devfabric/test_federation_pilot.py",
        "node --experimental-strip-types --test devfabric/cloudflare/test/federation_contract.test.ts devfabric/cloudflare/test/federation_tools.test.ts",
        "tsc --noEmit -p devfabric/cloudflare/tsconfig.core.json",
        "python -m metaengine.devfabric.isolated_suite_runner tests/devfabric --timeout-seconds 180",
        "python -m metaengine.devfabric.pytest_runner -q tests --ignore=tests/devfabric",
    ]

def test_pilot_runbook_requires_finalize_close_release_and_frozen_recovery() -> None:
    text = (ROOT / "chat_federation" / "PILOT_RUNBOOK.md").read_text(encoding="utf-8")
    for phrase in (
        "PASS_CANARY_MANUAL_RELAY -> FINALIZE -> CLOSED -> release witnesses -> frozen-cut recovery",
        "PASS_CANARY_MANUAL_RELAY is not PASS_MCP_CANARY",
        "IMMUTABLE_RECOVERY_CUT",
    ):
        assert phrase in text
