from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path, PurePosixPath

from metaengine.devfabric.capsule import _excluded, make_gate_receipt, verify_gate_receipt

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "devfabric" / "artifacts" / "manifests" / "connected-services.json"

EXPECTED = {
    "supabase",
    "create_state",
    "google_drive",
    "linear",
    "posthog",
    "neon",
    "replit",
    "antigravity",
}


def _walk_strings(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)
    elif isinstance(value, str):
        yield value


def test_connected_services_manifest_has_one_canonical_authority_and_fail_closed_external_policy():
    data = json.loads(MANIFEST.read_text())
    services = data["services"]
    assert set(services) == EXPECTED
    assert [name for name, item in services.items() if item["canonical_authority"]] == ["supabase"]
    assert services["supabase"]["health"] == "CONNECTED_READ_ONLY"
    assert services["create_state"]["health"] == "CONNECTED_READ_ONLY"
    assert services["google_drive"]["health"] == "CONNECTED_READ_ONLY"
    assert services["linear"]["health"] == "CONNECTED_READ_ONLY"
    assert services["posthog"]["health"] == "CONNECTED_READ_ONLY"
    assert services["neon"]["health"] == "RETIRED_BY_PROJECT_POLICY"
    assert services["replit"]["health"] == "CONNECTED_EXISTING_APPS_NEW_WORKER_BLOCKED_SUBSCRIPTION"
    assert services["antigravity"]["health"] == "OPTIONAL_CLI_UNAVAILABLE"
    assert all(not item["p3_allowed"] for item in services.values() if item["external"])
    assert data["actual_gate_writes"] == 0
    assert data["zero_spend"] is True


def test_connected_services_manifest_contains_no_secret_material_or_connection_strings():
    data = json.loads(MANIFEST.read_text())
    joined = "\n".join(_walk_strings(data)).lower()
    forbidden = (
        "password",
        "service_role",
        "api_key",
        "access_token",
        "refresh_token",
        "postgres://",
        "postgresql://",
        "sk-proj-",
        "-----begin private key-----",
    )
    for marker in forbidden:
        assert marker not in joined


def test_connected_status_cli_reads_static_health_manifest_without_contacting_connectors():
    proc = subprocess.run(
        [sys.executable, "-m", "metaengine.devfabric.cli", "connected-status", "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["stage"] == "C"
    assert payload["actual_gate_writes"] == 0
    assert payload["services"]["neon"]["health"] == "RETIRED_BY_PROJECT_POLICY"


def test_stage_c_gate_is_external_to_capsule_and_gate_version_is_verifiable(tmp_path):
    rel = PurePosixPath("devfabric/artifacts/manifests/stage-c-gate.json")
    assert _excluded(rel)
    receipt = make_gate_receipt(
        {"stage": "C", "certification_status": "BLOCKED_EXTERNAL_TOOLCHAIN"},
        gate_version="METAENGINE-DEVFABRIC-STAGE-C-GATE-1",
    )
    path = tmp_path / "stage-c-gate.json"
    path.write_text(json.dumps(receipt, sort_keys=True))
    result = verify_gate_receipt(path)
    assert result["status"] == "PASS"
    assert result["gate_version"] == "METAENGINE-DEVFABRIC-STAGE-C-GATE-1"
