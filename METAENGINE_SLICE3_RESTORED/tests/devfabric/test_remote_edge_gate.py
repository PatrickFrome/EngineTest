from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path, PurePosixPath

from metaengine.devfabric.capsule import _excluded, make_gate_receipt, verify_gate_receipt

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'devfabric' / 'artifacts' / 'manifests' / 'remote-edge.json'


def test_remote_edge_manifest_is_noncanonical_zero_spend_and_no_deploy():
    data = json.loads(MANIFEST.read_text())
    assert data['stage'] == 'D'
    assert data['canonical_authority'] is False
    assert data['zero_spend'] is True
    assert data['actual_cloud_writes'] == 0
    assert data['deployment'] == 'NO_DEPLOYMENT_PERFORMED'
    assert data['components']['d1']['data_class'] == 'EPHEMERAL_REFERENCES_ONLY'
    assert data['components']['r2']['addressing'] == 'SHA256_CONTENT_ADDRESSED'
    assert data['components']['workers_ai']['privacy_classes'] == ['P0', 'P1']
    assert data['components']['noodle']['status'] == 'NOT_BOOTSTRAPPED_NO_NOODLE_CLI'


def test_edge_status_cli_is_static_and_nonfatal():
    proc = subprocess.run(
        [sys.executable, '-m', 'metaengine.devfabric.cli', 'edge-status', '--json'],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload['stage'] == 'D'
    assert payload['actual_cloud_writes'] == 0
    assert payload['deployment'] == 'NO_DEPLOYMENT_PERFORMED'


def test_stage_d_gate_is_external_to_capsule_and_verifiable(tmp_path):
    assert _excluded(PurePosixPath('devfabric/artifacts/manifests/stage-d-gate.json'))
    receipt = make_gate_receipt(
        {'stage': 'D', 'certification_status': 'BLOCKED_EXTERNAL_NODE_TOOLCHAIN'},
        gate_version='METAENGINE-DEVFABRIC-STAGE-D-GATE-1',
    )
    path = tmp_path / 'stage-d-gate.json'
    path.write_text(json.dumps(receipt, sort_keys=True))
    result = verify_gate_receipt(path)
    assert result['status'] == 'PASS'
    assert result['gate_version'] == 'METAENGINE-DEVFABRIC-STAGE-D-GATE-1'


def test_edge_verifier_profile_covers_node_core_and_python_suites():
    import tomllib
    data = tomllib.loads((ROOT / 'devfabric' / 'verification' / 'profiles.toml').read_text())
    commands = data['profiles']['edge']['commands']
    joined = '\n'.join(commands)
    assert 'devfabric/cloudflare/test' in joined
    assert 'tsconfig.core.json' in joined
    assert 'tests/devfabric' in joined
    assert '--ignore=tests/devfabric' in joined


def test_node_toolchain_status_records_observed_offline_lock_blocker():
    status_path = ROOT / 'devfabric' / 'cloudflare' / 'TOOLCHAIN_STATUS.json'
    data = json.loads(status_path.read_text())
    assert data['package_lock'] == 'UNRESOLVED_OFFLINE'
    assert data['npm_probe']['command'] == 'npm install --package-lock-only --ignore-scripts --no-audit --no-fund'
    assert data['npm_probe']['exit_code'] == 124
    assert data['npm_probe']['package_lock_created'] is False
    assert not (ROOT / 'devfabric' / 'cloudflare' / 'package-lock.json').exists()


def test_edge_verifier_profile_covers_federation_mcp_contracts():
    import tomllib
    data = tomllib.loads((ROOT / 'devfabric' / 'verification' / 'profiles.toml').read_text())
    joined = '\n'.join(data['profiles']['edge']['commands'])
    assert 'federation_contract.test.ts' in joined
    assert 'federation_tools.test.ts' in joined
    tsconfig = (ROOT / 'devfabric' / 'cloudflare' / 'tsconfig.core.json').read_text()
    assert 'src/federation_contract.ts' in tsconfig
    assert 'src/federation_client.ts' in tsconfig
    assert 'src/federation_tools.ts' in tsconfig


def test_mcp_source_registers_exact_federation_surface_without_internal_control_plane():
    import re
    source = (ROOT / 'devfabric' / 'cloudflare' / 'src' / 'mcp.ts').read_text()
    names = re.findall(r"server\.registerTool\('([^']+)'", source)
    expected = [
        'federation_status','slot_catalog','session_status','epoch_status','task_get','task_dependencies',
        'candidate_status','conflict_status','sync_snapshot_get','federation_register','session_release',
        'task_claim','task_progress','candidate_submit','review_submit','conflict_submit','integration_propose',
        'sync_snapshot_publish',
    ]
    assert [name for name in names if name in expected] == expected
    for forbidden in ('open_epoch','seed_task','seed_role','reclaim_slot','sql','shell','promote','champion','secret'):
        assert forbidden not in names
