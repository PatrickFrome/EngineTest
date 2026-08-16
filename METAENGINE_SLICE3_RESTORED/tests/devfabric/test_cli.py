import json
from pathlib import Path
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[2]


def run(*args):
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True)


def test_new_and_existing_cli_help_are_available():
    new = run("python", "-m", "metaengine.devfabric.cli", "--help")
    old = run("python", "-m", "metaengine.cli", "--help")
    assert new.returncode == 0, new.stderr
    assert old.returncode == 0, old.stderr
    assert "doctor" in new.stdout
    assert "capsule-build" in new.stdout
    assert "run" in old.stdout


def test_pyproject_declares_additive_metaengine_dev_command():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert data["project"]["scripts"]["metaengine-dev"] == "metaengine.devfabric.cli:main"


def test_doctor_json_command_is_offline_safe():
    cp = run("python", "-m", "metaengine.devfabric.cli", "doctor", "--profile", "offline", "--json")
    assert cp.returncode in (0, 3)
    payload = __import__("json").loads(cp.stdout)
    assert payload["profile"] == "offline"
    assert payload["requires_cloud_credentials"] is False


def test_task_create_emits_immutable_task_json():
    cp = run(
        "python", "-m", "metaengine.devfabric.cli", "task-create",
        "--objective", "test objective",
        "--source-checkpoint", "cp001",
        "--source-tree-hash", "a" * 64,
        "--capability", "CODE_GENERATOR",
    )
    assert cp.returncode == 0, cp.stderr
    payload = __import__("json").loads(cp.stdout)
    assert payload["task_id"].startswith("task-")
    assert payload["zero_spend"] is True

def test_swarm_status_json_is_nonfatal_when_optional_tools_are_missing():
    cp = run('python','-m','metaengine.devfabric.cli','swarm-status','--json')
    assert cp.returncode == 0
    payload = json.loads(cp.stdout)
    assert payload['profile'] == 'ai-swarm'
    assert payload['status'] in {'OPTIONAL_PROVIDER_UNAVAILABLE','PARTIAL','READY'}


def test_federation_status_and_role_show_are_static_and_role_scoped():
    status = run("python", "-m", "metaengine.devfabric.cli", "federation-status", "--json")
    assert status.returncode == 0, status.stderr
    payload = json.loads(status.stdout)
    assert payload["protocol_version"] == "D6.1"
    assert payload["slot_count"] == 8
    assert set(payload["role_profile_hashes"]) == {f"C{i}" for i in range(8)}
    assert payload["canonical_authority"] == "SUPABASE_ONLY"

    role = run("python", "-m", "metaengine.devfabric.cli", "role-show", "C4", "--json")
    assert role.returncode == 0, role.stderr
    role_payload = json.loads(role.stdout)
    assert role_payload["slot_id"] == "C4"
    assert role_payload["role"] == "EDGE_MCP"
    assert role_payload["role_genome"]["hard"]["slot"] == "C4"
    assert "C3" not in json.dumps(role_payload)


def test_federation_bootstrap_defaults_to_frozen_offline_read_only_packet():
    cp = run("python", "-m", "metaengine.devfabric.cli", "federation-bootstrap", "--slot", "C4", "--json")
    assert cp.returncode == 0, cp.stderr
    payload = json.loads(cp.stdout)
    assert payload["federation_state"] == "FROZEN_OFFLINE"
    assert payload["slot_id"] == "C4"
    assert "session_id" not in payload
    assert "epoch_id" not in payload
    assert "lease_generation" not in payload


def test_federation_sim_register_requires_explicit_local_db_and_uses_verified_role_hash(tmp_path):
    from metaengine.devfabric.federation.store import FederationStore

    db = tmp_path / "federation.sqlite3"
    store = FederationStore(db)
    store.put_epoch(epoch_id="e-cli", base_checkpoint_id="cp1", policy_hash="a" * 64, catalog_hash="b" * 64)
    store.close()

    missing = run(
        "python", "-m", "metaengine.devfabric.cli", "federation-sim-register",
        "--epoch", "e-cli", "--slot", "C4", "--capsule-sha256", "c" * 64,
        "--registration-nonce", "cli-c4", "--json",
    )
    assert missing.returncode == 2

    cp = run(
        "python", "-m", "metaengine.devfabric.cli", "federation-sim-register",
        "--db", str(db), "--epoch", "e-cli", "--slot", "C4",
        "--capsule-sha256", "c" * 64, "--registration-nonce", "cli-c4", "--json",
    )
    assert cp.returncode == 0, cp.stderr
    payload = json.loads(cp.stdout)
    assert payload["slot_id"] == "C4"

    status = run("python", "-m", "metaengine.devfabric.cli", "federation-status", "--json")
    expected = json.loads(status.stdout)["role_profile_hashes"]["C4"]
    assert payload["role_profile_hash"] == expected


def test_federation_sim_auto_registration_selects_matching_profile_after_slot_selection(tmp_path):
    from metaengine.devfabric.federation.store import FederationStore

    db = tmp_path / "federation.sqlite3"
    store = FederationStore(db)
    store.put_epoch(epoch_id="e-auto", base_checkpoint_id="cp1", policy_hash="a" * 64, catalog_hash="b" * 64)
    store.close()
    status = run("python", "-m", "metaengine.devfabric.cli", "federation-status", "--json")
    hashes = json.loads(status.stdout)["role_profile_hashes"]

    first = run(
        "python", "-m", "metaengine.devfabric.cli", "federation-sim-register",
        "--db", str(db), "--epoch", "e-auto", "--slot", "AUTO",
        "--capsule-sha256", "c" * 64, "--registration-nonce", "auto-1", "--json",
    )
    second = run(
        "python", "-m", "metaengine.devfabric.cli", "federation-sim-register",
        "--db", str(db), "--epoch", "e-auto", "--slot", "AUTO",
        "--capsule-sha256", "c" * 64, "--registration-nonce", "auto-2", "--json",
    )
    assert first.returncode == second.returncode == 0
    one, two = json.loads(first.stdout), json.loads(second.stdout)
    assert one["slot_id"] == "C0"
    assert one["role_profile_hash"] == hashes["C0"]
    assert two["slot_id"] == "C1"
    assert two["role_profile_hash"] == hashes["C1"]
