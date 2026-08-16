from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "architecture_source_registry.py"
REVISION = "1" * 40


def _claim(claim_id: str):
    return {
        "claim_id": claim_id,
        "kind": "PUBLISHER_CLAIM",
        "statement": "The publisher documents conditional routing.",
        "evidence_locator": "https://example.invalid/README.md",
    }


def _mechanism():
    return {
        "mechanism_id": "conditional-routing",
        "status": "A1_MECHANISM_HYPOTHESIS",
        "semantic_definition": "Route only a bounded subset of workers for a request.",
        "source_fact_boundary": "The public documentation describes conditional routing.",
        "hypothesized_effect": "Reduce marginal compute while preserving task quality.",
        "falsification_test": "Compare routed and dense baselines under a fixed budget.",
    }


def _permissive_source():
    return {
        "source_id": "fixture-open-source",
        "publisher": "Fixture Publisher",
        "system_name": "Fixture Open Model",
        "version": "fixture-v1",
        "source_class": "PERMISSIVE_CODE",
        "ingestion_status": "INGESTED",
        "official_source_locator": "https://example.invalid/open",
        "exact_commit_or_release": REVISION,
        "retrieved_at": "2026-08-13T12:00:00Z",
        "license_name": "MIT License",
        "license_expression": "MIT",
        "license_evidence_locator": "https://example.invalid/open/LICENSE",
        "license_relative_path": "LICENSE",
        "allowed_use": ["ANALYSIS", "REFERENCE", "CLEAN_ROOM_REIMPLEMENTATION"],
        "forbidden_use": ["AUTOMATIC_PROMOTION", "AUTOMATIC_RUNTIME_DEPENDENCY"],
        "epistemic_ceiling": "A1_MECHANISM_HYPOTHESIS",
        "architecture_claims": [_claim("open-routing-claim")],
        "mechanism_candidates": [_mechanism()],
        "blockers": [],
        "files": [
            {
                "staged_path": "README.md",
                "relative_path": "README.md",
                "media_type": "text/markdown",
                "git_blob_id": None,
                "source_revision": REVISION,
            },
            {
                "staged_path": "LICENSE",
                "relative_path": "LICENSE",
                "media_type": "text/plain",
                "git_blob_id": None,
                "source_revision": REVISION,
            },
        ],
    }


def _closed_source():
    return {
        "source_id": "fixture-closed-public",
        "publisher": "Closed Publisher",
        "system_name": "Closed Model",
        "version": "public-docs-2026-08-13",
        "source_class": "CLOSED_BEHAVIORAL_ONLY",
        "ingestion_status": "REGISTERED_ONLY",
        "official_source_locator": "https://example.invalid/closed",
        "exact_commit_or_release": "public-docs-retrieved-2026-08-13",
        "retrieved_at": "2026-08-13T12:00:00Z",
        "license_name": "Proprietary public documentation",
        "license_expression": "LicenseRef-Proprietary-Public-Documentation",
        "license_evidence_locator": "https://example.invalid/terms",
        "license_relative_path": None,
        "allowed_use": ["BEHAVIORAL_REFERENCE"],
        "forbidden_use": ["INTERNAL_ARCHITECTURE_FACT", "RUNTIME_DEPENDENCY"],
        "epistemic_ceiling": "A1_MECHANISM_HYPOTHESIS",
        "architecture_claims": [_claim("closed-public-claim")],
        "mechanism_candidates": [],
        "blockers": [],
        "files": [],
    }


def _write_fixture(base: Path, *, sources=None):
    staging = base / "staging"
    source_staging = staging / "fixture-open-source"
    source_staging.mkdir(parents=True)
    (source_staging / "LICENSE").write_bytes(b"MIT\n")
    (source_staging / "README.md").write_bytes(b"# Fixture\n")
    catalog = base / "catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "catalog_version": "ARCHITECTURE-SOURCE-CATALOG-1",
                "sources": sources if sources is not None else [_permissive_source(), _closed_source()],
            }
        )
    )
    return catalog, staging, base / "vault", base / "output"


def _run(*args):
    return subprocess.run(
        (sys.executable, str(SCRIPT), *map(str, args)),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _ingest(catalog, staging, vault, output):
    return _run(
        "ingest",
        "--catalog",
        catalog,
        "--staging-root",
        staging,
        "--vault-root",
        vault,
        "--output-root",
        output,
    )


def test_cli_ingest_and_verify_are_portable_deterministic_and_independently_checkable(tmp_path):
    first = _write_fixture(tmp_path / "first")
    second = _write_fixture(tmp_path / "second")

    first_result = _ingest(*first)
    second_result = _ingest(*second)

    assert first_result.returncode == 0, first_result.stderr
    assert second_result.returncode == 0, second_result.stderr
    first_payload = json.loads(first_result.stdout)
    second_payload = json.loads(second_result.stdout)
    assert first_payload == second_payload
    assert first_payload["status"] == "PASS"
    assert first_payload["source_count"] == 2
    assert first_payload["ingested_source_count"] == 1
    assert first_payload["verified_blob_count"] == 2

    first_output = first[3]
    serialized_outputs = "".join(
        path.read_text()
        for path in sorted(first_output.rglob("*.json"))
    )
    assert str(tmp_path) not in serialized_outputs
    assert (first_output / "sources" / "fixture-open-source.json").is_file()
    assert (first_output / "sources" / "fixture-closed-public.json").is_file()
    assert (first_output / "packs" / "fixture-open-source.json").is_file()
    assert (first_output / "receipts" / "fixture-open-source.json").is_file()
    assert (first_output / "mechanisms" / "conditional-routing.json").is_file()

    verify = _run(
        "verify",
        "--registry",
        first_output / "registry.json",
        "--vault-root",
        first[2],
    )
    assert verify.returncode == 0, verify.stderr
    assert json.loads(verify.stdout) == first_payload


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    (
        ("missing_stage_file", "STAGED_FILE_MISSING"),
        ("revision_mismatch", "SOURCE_REVISION_MISMATCH"),
        ("closed_staged_bytes", "CLOSED_SOURCE_BYTES_FORBIDDEN"),
        ("permissive_empty", "PERMISSIVE_PACK_EMPTY"),
    ),
)
def test_cli_fails_without_emitting_a_pass_registry(tmp_path, mutation, expected_code):
    permissive = _permissive_source()
    closed = _closed_source()
    sources = [permissive, closed]
    catalog, staging, vault, output = _write_fixture(tmp_path / mutation, sources=sources)
    if mutation == "missing_stage_file":
        (staging / "fixture-open-source" / "README.md").unlink()
    elif mutation == "revision_mismatch":
        permissive["files"][0]["source_revision"] = "2" * 40
        catalog.write_text(json.dumps({"catalog_version": "ARCHITECTURE-SOURCE-CATALOG-1", "sources": sources}))
    elif mutation == "closed_staged_bytes":
        closed["files"] = [
            {
                "staged_path": "README.md",
                "relative_path": "README.md",
                "media_type": "text/markdown",
                "git_blob_id": None,
                "source_revision": closed["exact_commit_or_release"],
            }
        ]
        (staging / "fixture-closed-public").mkdir()
        (staging / "fixture-closed-public" / "README.md").write_text("closed docs")
        catalog.write_text(json.dumps({"catalog_version": "ARCHITECTURE-SOURCE-CATALOG-1", "sources": sources}))
    elif mutation == "permissive_empty":
        permissive["files"] = []
        permissive["license_relative_path"] = None
        catalog.write_text(json.dumps({"catalog_version": "ARCHITECTURE-SOURCE-CATALOG-1", "sources": sources}))

    result = _ingest(catalog, staging, vault, output)

    assert result.returncode != 0
    assert json.loads(result.stdout)["findings"][0]["code"] == expected_code
    assert not (output / "registry.json").exists()


def test_cli_verify_rejects_a_mutated_vault_blob(tmp_path):
    catalog, staging, vault_root, output = _write_fixture(tmp_path / "mutated")
    ingest = _ingest(catalog, staging, vault_root, output)
    assert ingest.returncode == 0, ingest.stderr
    registry = json.loads((output / "registry.json").read_text())
    pack = json.loads((output / "packs" / "fixture-open-source.json").read_text())
    digest = pack["blob_descriptors"][0]["digest"]
    blob = vault_root / "blobs" / "sha256" / digest
    blob.chmod(0o644)
    blob.write_bytes(b"mutated")

    verify = _run("verify", "--registry", output / "registry.json", "--vault-root", vault_root)

    assert verify.returncode != 0
    payload = json.loads(verify.stdout)
    assert payload["status"] == "FAIL"
    assert payload["registry_snapshot_sha256"] == registry["registry_snapshot_sha256"]
    assert {finding["code"] for finding in payload["findings"]} == {"HASH_MISMATCH"}


def test_cli_verify_rejects_a_self_consistent_but_stale_pass_receipt(tmp_path):
    catalog, staging, vault_root, output = _write_fixture(tmp_path / "stale-receipt")
    ingest = _ingest(catalog, staging, vault_root, output)
    assert ingest.returncode == 0, ingest.stderr
    receipt_path = output / "receipts" / "fixture-open-source.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["verified_blob_count"] = 1
    receipt["verified_total_bytes"] = 4
    payload = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    receipt_path.write_text(json.dumps(receipt))

    verify = _run("verify", "--registry", output / "registry.json", "--vault-root", vault_root)

    assert verify.returncode != 0
    assert {finding["code"] for finding in json.loads(verify.stdout)["findings"]} == {
        "VERIFICATION_RECEIPT_STALE"
    }
