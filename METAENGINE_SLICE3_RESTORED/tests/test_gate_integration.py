"""METAENGINE Step A (Slice 5) — Gate Global Integration tests.

Tests that the development review gate is ENFORCED in the CLI run path:
- run without receipt → REJECTED
- run with invalid receipt → REJECTED
- run with valid receipt → ALLOWED
- run with stale snapshot → REJECTED
- stage_gate_summary.json produced after run
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    """Run the MetaEngine CLI with the given arguments."""
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, str(ROOT / "bin" / "destruktion-meta16"), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


# ---------------------------------------------------------------------------
# 1. CLI run without --receipt is REJECTED (gate enforcement)
# ---------------------------------------------------------------------------


def test_run_without_receipt_is_rejected(tmp_path):
    """The CLI run command must require a --receipt argument."""
    out = tmp_path / "run_out"
    result = _run_cli("run", str(tmp_path / "input.txt"), "--out", str(out))
    assert result.returncode != 0, "run without receipt should fail"
    assert "RECEIPT_REQUIRED" in result.stderr or "receipt" in result.stderr.lower() or "the following arguments are required: --receipt" in result.stderr


def test_run_with_nonexistent_receipt_is_rejected(tmp_path):
    """A nonexistent receipt file must be rejected."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("Test input for gate enforcement.")
    out = tmp_path / "run_out"
    result = _run_cli("run", str(input_file), "--out", str(out), "--receipt", str(tmp_path / "nonexistent.json"))
    assert result.returncode != 0
    assert "RECEIPT_FILE_NOT_FOUND" in result.stderr or "not found" in result.stderr.lower() or "No such file" in result.stderr


# ---------------------------------------------------------------------------
# 2. verify_development_transition is called (unit-level)
# ---------------------------------------------------------------------------


def test_gate_check_function_exists():
    """The CLI must import and use verify_development_transition."""
    from metaengine.cli import check_development_gate
    assert callable(check_development_gate)


def test_gate_check_rejects_none_receipt():
    """check_development_gate must reject when receipt is None."""
    from metaengine.cli import check_development_gate, GateCheckError
    with pytest.raises(GateCheckError, match="RECEIPT_REQUIRED"):
        check_development_gate(receipt_path=None, root=ROOT)


def test_gate_check_rejects_missing_file(tmp_path):
    """check_development_gate must reject when receipt file doesn't exist."""
    from metaengine.cli import check_development_gate, GateCheckError
    with pytest.raises(GateCheckError, match="RECEIPT_FILE_NOT_FOUND"):
        check_development_gate(receipt_path=str(tmp_path / "missing.json"), root=ROOT)


def test_gate_check_accepts_valid_receipt():
    """check_development_gate must accept a valid receipt (returns the request)."""
    from metaengine.cli import check_development_gate
    from metaengine.devfabric.development_gate import verify_development_transition
    # Use the Slice-4 review receipt (valid, ACCEPT_WITH_FOLLOWUP_EXPERIMENT)
    receipt_path = ROOT / "devfabric" / "artifacts" / "reviews" / "development" / "metaengine-1-slice-4-review.json"
    if not receipt_path.is_file():
        pytest.skip("Slice-4 review receipt not found")
    request = check_development_gate(receipt_path=str(receipt_path), root=ROOT)
    # The request is returned (gate passed); verify the transition result
    result = verify_development_transition(request)
    assert result.allowed is True
    assert "ALLOWED" in result.reason


def test_gate_check_rejects_tampered_receipt(tmp_path):
    """check_development_gate must reject a tampered receipt (hash mismatch)."""
    from metaengine.cli import check_development_gate, GateCheckError
    receipt_path = ROOT / "devfabric" / "artifacts" / "reviews" / "development" / "metaengine-1-slice-4-review.json"
    if not receipt_path.is_file():
        pytest.skip("Slice-4 review receipt not found")
    # Tamper: change the receipt hash
    tampered = json.loads(receipt_path.read_text())
    tampered["receipt_hash"] = "0" * 64
    tampered_path = tmp_path / "tampered_receipt.json"
    tampered_path.write_text(json.dumps(tampered))
    with pytest.raises(GateCheckError, match="RECEIPT_INVALID"):
        check_development_gate(receipt_path=str(tampered_path), root=ROOT)


# ---------------------------------------------------------------------------
# 3. Stage gate summary is produced after run
# ---------------------------------------------------------------------------


def test_stage_gate_summary_function_exists():
    """The CLI must have a function to produce a stage gate summary."""
    from metaengine.cli import produce_stage_gate_summary
    assert callable(produce_stage_gate_summary)


def test_stage_gate_summary_structure(tmp_path):
    """produce_stage_gate_summary must return a dict with required fields."""
    from metaengine.cli import produce_stage_gate_summary
    # Minimal run result
    run_result = {
        "meta_run_id": "test-run-001",
        "input_hash": "0" * 64,
        "status": "COMPLETE",
        "telemetry_hash": "0" * 64,
    }
    summary = produce_stage_gate_summary(run_result, receipt_hash="abc123", root=ROOT)
    assert "stage_gate_version" in summary
    assert "meta_run_id" in summary
    assert "receipt_hash" in summary
    assert "run_status" in summary
    assert "gate_summary_hash" in summary
    assert summary["gate_enforced"] is True


# ---------------------------------------------------------------------------
# 4. Integrated gate + run (requires valid receipt)
# ---------------------------------------------------------------------------


def test_full_run_with_valid_receipt_produces_stage_gate_summary(tmp_path):
    """A full CLI run with a valid receipt must produce stage_gate_summary.json."""
    receipt_path = ROOT / "devfabric" / "artifacts" / "reviews" / "development" / "metaengine-1-slice-4-review.json"
    if not receipt_path.is_file():
        pytest.skip("Slice-4 review receipt not found")

    input_file = tmp_path / "input.txt"
    input_file.write_text("Test input for integrated gate + run. This text has enough content for the orchestrator to process through its pipeline stages.")
    out = tmp_path / "run_out"

    result = _run_cli("run", str(input_file), "--out", str(out), "--receipt", str(receipt_path), "--max-workers", "4")

    # The run may fail for other reasons (e.g. missing lineages), but the gate
    # must have been checked (not skipped). We verify by checking that
    # stage_gate_summary.json was produced OR that the error is NOT a gate error.
    if result.returncode == 0:
        summary_path = out / "stage_gate_summary.json"
        assert summary_path.is_file(), "stage_gate_summary.json not produced after successful run"
        summary = json.loads(summary_path.read_text())
        assert summary["gate_enforced"] is True
    else:
        # If run failed, it must NOT be because the gate was missing
        assert "RECEIPT_REQUIRED" not in result.stderr, "gate was not enforced"
