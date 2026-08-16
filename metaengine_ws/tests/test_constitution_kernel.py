from __future__ import annotations

import json
from pathlib import Path

import pytest

from metaengine.constitution import load_constitution_kernel, verify_constitution_conformance
from metaengine.security import IMMUTABLE_GUARDRAILS, IMMUTABLE_GUARDRAIL_HASH


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_K0_IDS = {
    "PROVENANCE_PRIMARY_EVIDENCE",
    "CANONICAL_NOT_SCIENTIFIC_TRUTH",
    "NO_TRUTH_FROM_RANKING_OR_VOTING",
    "PRESERVE_ABSTENTION",
    "MUTATION_REQUIRES_RECEIPT",
    "SEPARATE_GENERATION_AND_PROMOTION",
    "FROZEN_EVALUATION_CONTRACT",
    "NO_NORMAL_KERNEL_SELF_MUTATION",
    "NO_EXECUTABLE_SELF_MODIFICATION",
    "PRIVACY_PERMISSION_FAIL_CLOSED",
    "IMMUTABLE_HISTORY_WITH_SUPERSESSION",
    "ROLLBACK_RECOVERY_REQUIRED",
}


def _copy_kernel_config(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    target = root / "config" / "constitution"
    target.mkdir(parents=True)
    source = ROOT / "config" / "constitution"
    for name in ("k0_v1.json", "k1_v1.json", "conformance_matrix_v1.json"):
        (target / name).write_bytes((source / name).read_bytes())
    matrix = json.loads((target / "conformance_matrix_v1.json").read_text())
    refs = {ref.split("#", 1)[0] for entry in matrix["entries"] for key in ("enforcement_refs", "test_refs") for ref in entry[key]}
    for rel in sorted(refs):
        src = ROOT / rel
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
    return root


def test_kernel_has_exact_k0_invariants_and_deterministic_hash():
    left = load_constitution_kernel(ROOT)
    right = load_constitution_kernel(ROOT)
    assert {item.invariant_id for item in left.k0_invariants} == EXPECTED_K0_IDS
    assert len(left.k0_invariants) == 12
    assert left.k0_hash == right.k0_hash
    assert left.k1_hash == right.k1_hash
    assert left.constitution_hash == right.constitution_hash
    assert len(left.constitution_hash) == 64


def test_normal_evolution_has_no_constitution_amendment_authority():
    kernel = load_constitution_kernel(ROOT)
    assert kernel.amendment_boundary.ordinary_evolution_allowed is False
    assert kernel.amendment_boundary.authority_status == "NOT_IMPLEMENTED"
    with pytest.raises(RuntimeError, match="CONSTITUTION_AMENDMENT_AUTHORITY_NOT_IMPLEMENTED"):
        kernel.require_amendment_authority()


def test_duplicate_k0_invariant_fails_closed(tmp_path):
    root = _copy_kernel_config(tmp_path)
    path = root / "config" / "constitution" / "k0_v1.json"
    value = json.loads(path.read_text())
    value["invariants"].append(dict(value["invariants"][0]))
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="CONSTITUTION_K0_DUPLICATE_INVARIANT"):
        load_constitution_kernel(root)


def test_missing_k0_invariant_fails_closed(tmp_path):
    root = _copy_kernel_config(tmp_path)
    path = root / "config" / "constitution" / "k0_v1.json"
    value = json.loads(path.read_text())
    value["invariants"] = value["invariants"][:-1]
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="CONSTITUTION_K0_SET_MISMATCH"):
        load_constitution_kernel(root)


def test_empty_k1_topic_fails_closed(tmp_path):
    root = _copy_kernel_config(tmp_path)
    path = root / "config" / "constitution" / "k1_v1.json"
    value = json.loads(path.read_text())
    value["topics"][0] = ""
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="CONSTITUTION_K1_TOPIC_INVALID"):
        load_constitution_kernel(root)


def test_conformance_matrix_covers_every_k0_invariant_once():
    report = verify_constitution_conformance(ROOT)
    assert report.valid is True
    assert report.mapped_invariant_count == 12
    assert report.unmapped_invariants == ()
    assert report.duplicate_invariants == ()
    assert len(report.report_hash) == 64


def test_conformance_matrix_requires_enforcement_and_test_refs(tmp_path):
    root = _copy_kernel_config(tmp_path)
    path = root / "config" / "constitution" / "conformance_matrix_v1.json"
    value = json.loads(path.read_text())
    value["entries"][0]["enforcement_refs"] = []
    path.write_text(json.dumps(value))
    report = verify_constitution_conformance(root)
    assert report.valid is False
    assert "CONSTITUTION_CONFORMANCE_ENFORCEMENT_REF_REQUIRED" in report.findings


def test_conformance_matrix_rejects_missing_and_duplicate_invariants(tmp_path):
    root = _copy_kernel_config(tmp_path)
    path = root / "config" / "constitution" / "conformance_matrix_v1.json"
    value = json.loads(path.read_text())
    missing = dict(value)
    missing["entries"] = value["entries"][:-1]
    path.write_text(json.dumps(missing))
    report = verify_constitution_conformance(root)
    assert report.valid is False
    assert report.unmapped_invariants
    value["entries"].append(dict(value["entries"][0]))
    path.write_text(json.dumps(value))
    report = verify_constitution_conformance(root)
    assert report.valid is False
    assert report.duplicate_invariants


def test_conformance_matrix_rejects_missing_repository_path(tmp_path):
    root = _copy_kernel_config(tmp_path)
    path = root / "config" / "constitution" / "conformance_matrix_v1.json"
    value = json.loads(path.read_text())
    value["entries"][0]["test_refs"] = ["tests/does_not_exist.py#test_missing"]
    path.write_text(json.dumps(value))
    report = verify_constitution_conformance(root)
    assert report.valid is False
    assert "CONSTITUTION_CONFORMANCE_REF_PATH_MISSING" in report.findings


def test_legacy_guardrails_are_all_mapped_into_k0_without_hash_drift():
    kernel = load_constitution_kernel(ROOT)
    mapped = {guardrail for invariant in kernel.k0_invariants for guardrail in invariant.legacy_guardrail_ids}
    assert set(IMMUTABLE_GUARDRAILS) <= mapped
    assert IMMUTABLE_GUARDRAIL_HASH == "7ca26b082e1c4dc1de5f3d098f957d0330a5b9f2cf70da12160a672c01a2eb38"
