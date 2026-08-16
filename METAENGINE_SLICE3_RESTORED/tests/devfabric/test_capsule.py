from pathlib import Path
import hashlib
import zipfile

from metaengine.devfabric.capsule import build_control_capsule, verify_control_capsule

ROOT = Path(__file__).resolve().parents[2]


def test_control_capsule_is_deterministic_self_verifying_and_secret_free(tmp_path):
    one = tmp_path / "one.zip"
    two = tmp_path / "two.zip"
    first = build_control_capsule(ROOT, one)
    second = build_control_capsule(ROOT, two)
    assert first["capsule_sha256"] == second["capsule_sha256"]
    assert hashlib.sha256(one.read_bytes()).hexdigest() == first["capsule_sha256"]

    result = verify_control_capsule(one)
    assert result["status"] == "PASS"
    assert result["bad"] == []
    assert result["missing"] == []
    assert result["extra"] == []
    assert result["secret_hits"] == []

    with zipfile.ZipFile(one) as zf:
        names = set(zf.namelist())
    assert "devfabric/LINEAGE_LOCK_SHA256.txt" in names
    assert not any(name.startswith("lineages/") for name in names)


def test_reference_vault_bytes_are_external_to_control_payload(tmp_path):
    from metaengine.devfabric.capsule import _payload_paths

    tracked = tmp_path / "tracked.txt"
    tracked.write_text("tracked metadata")
    vault_blob = tmp_path / "reference-vault" / "blobs" / "sha256" / ("a" * 64)
    vault_blob.parent.mkdir(parents=True)
    vault_blob.write_bytes(b"foreign bytes")

    relative_paths = {path.relative_to(tmp_path).as_posix() for path in _payload_paths(tmp_path)}

    assert relative_paths == {"tracked.txt"}


def test_stage_gate_attestation_is_external_to_capsule_to_avoid_hash_cycle():
    from pathlib import PurePosixPath
    from metaengine.devfabric.capsule import _excluded

    assert _excluded(PurePosixPath("devfabric/artifacts/manifests/stage-a-gate.json"))

def test_stage_b_gate_attestation_is_external_to_capsule_to_avoid_hash_cycle():
    from pathlib import PurePosixPath
    from metaengine.devfabric.capsule import _excluded
    assert _excluded(PurePosixPath('devfabric/artifacts/manifests/stage-b-gate.json'))


def test_stage_d_cloudflare_runtime_state_and_secrets_are_external_to_capsule():
    from pathlib import PurePosixPath
    from metaengine.devfabric.capsule import _excluded

    assert _excluded(PurePosixPath('devfabric/cloudflare/node_modules/pkg/index.js'))
    assert _excluded(PurePosixPath('devfabric/cloudflare/.wrangler/state/v3/d1.sqlite'))
    assert _excluded(PurePosixPath('devfabric/cloudflare/.dev.vars'))
    assert not _excluded(PurePosixPath('devfabric/cloudflare/.dev.vars.example'))


def test_stage_d6_static_federation_is_portable_but_runtime_state_is_external(tmp_path):
    from metaengine.devfabric.federation.bootstrap import load_bootstrap

    capsule = tmp_path / "d6c.zip"
    build_control_capsule(ROOT, capsule)
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(capsule) as zf:
        names = set(zf.namelist())
        zf.extractall(extracted)

    expected_static = {
        "chat_federation/ROLE_CATALOG.json",
        *{f"chat_federation/ROLE_GENOMES/C{i}.json" for i in range(8)},
        "chat_federation/FEDERATION_PROTOCOL.json",
        "chat_federation/TASK_PROTOCOL.json",
        "chat_federation/LEASE_PROTOCOL.json",
        "chat_federation/EPOCH_PROTOCOL.json",
        "chat_federation/CONFLICT_POLICY.json",
        "chat_federation/ADAPTATION_POLICY.json",
        "chat_federation/BOOTSTRAP.md",
    }
    assert expected_static <= names
    assert not any(name.startswith("devfabric/state/") and name != "devfabric/state/.gitkeep" for name in names)
    assert not any(name.endswith("federation.sqlite3") or name.endswith("session.json") for name in names)

    context = load_bootstrap(extracted)
    assert context.protocol_version == "D6.1"
    assert context.slot_count == 8


def test_stage_d6_gate_attestation_is_external_to_capsule_to_avoid_hash_cycle():
    from pathlib import PurePosixPath
    from metaengine.devfabric.capsule import _excluded

    assert _excluded(PurePosixPath("devfabric/artifacts/manifests/stage-d6-gate.json"))


def test_stage_d6_g1_gate_attestation_is_external_to_capsule_to_avoid_hash_cycle():
    from pathlib import PurePosixPath
    from metaengine.devfabric.capsule import _excluded

    assert _excluded(PurePosixPath("devfabric/artifacts/manifests/stage-d6-g1-gate.json"))
