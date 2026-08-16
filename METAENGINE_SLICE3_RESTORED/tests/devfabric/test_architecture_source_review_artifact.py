import json
import shutil
from pathlib import Path

from metaengine.devfabric.development_review import ContentSnapshot, DevelopmentReviewContext, load_bootstrap_review_context


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "development_review_bootstrap_v1.json"


REQUIRED_ARCHITECTURE_LIBRARY_PATHS = {
    "docs/superpowers/specs/2026-08-13-metaengine-1-slice3-source-registry-vault-design.md",
    "schemas/architecture_source_record.schema.json",
    "schemas/reference_vault_pack.schema.json",
    "research/architecture_library/registry.json",
    "research/architecture_library/retrieval_evidence.json",
    "devfabric/artifacts/reviews/development/evidence/metaengine-1-slice-3-task-1-contracts.json",
    "devfabric/artifacts/reviews/development/evidence/metaengine-1-slice-3-task-2-vault.json",
    "devfabric/artifacts/reviews/development/evidence/metaengine-1-slice-3-task-3-builder.json",
    "devfabric/artifacts/reviews/development/evidence/metaengine-1-slice-3-task-4-first-wave.json",
}


def _config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _copy_bootstrap_context(tmp_path: Path) -> None:
    config = _config()
    target_config = tmp_path / "config" / "development_review_bootstrap_v1.json"
    target_config.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CONFIG_PATH, target_config)
    for domain in ("constitution_paths", "architecture_library_paths", "policy_paths"):
        for rel in config[domain]:
            source = PROJECT_ROOT / rel
            target = tmp_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def test_slice3_architecture_library_snapshot_binds_registry_design_schemas_and_receipts():
    configured = set(_config()["architecture_library_paths"])
    assert REQUIRED_ARCHITECTURE_LIBRARY_PATHS <= configured
    assert any(path.startswith("research/architecture_library/sources/") for path in configured)
    assert any(path.startswith("research/architecture_library/mechanisms/") for path in configured)
    assert any(path.startswith("research/architecture_library/packs/") for path in configured)
    assert any(path.startswith("research/architecture_library/receipts/") for path in configured)


def test_slice3_source_card_change_makes_architecture_library_snapshot_stale(tmp_path):
    _copy_bootstrap_context(tmp_path)
    before = load_bootstrap_review_context(tmp_path).architecture_library.snapshot_hash
    source_card = tmp_path / "research" / "architecture_library" / "sources" / "deepseek-v3.2-exp-87e509a.json"
    source_card.write_bytes(source_card.read_bytes() + b"\n")
    after = load_bootstrap_review_context(tmp_path).architecture_library.snapshot_hash
    assert after != before

from metaengine.devfabric.development_gate import DevelopmentTransitionRequest, verify_development_transition
from metaengine.devfabric.development_review import DevelopmentEvolutionReviewReceipt, verify_receipt_integrity

SLICE3_RECEIPT_PATH = (
    PROJECT_ROOT
    / "devfabric"
    / "artifacts"
    / "reviews"
    / "development"
    / "metaengine-1-slice-3-review.json"
)


def _slice3_receipt() -> DevelopmentEvolutionReviewReceipt:
    return DevelopmentEvolutionReviewReceipt.from_dict(
        json.loads(SLICE3_RECEIPT_PATH.read_text(encoding="utf-8"))
    )


def test_slice3_final_review_receipt_admits_only_current_slice4_context():
    receipt = _slice3_receipt()
    assert verify_receipt_integrity(receipt).valid is True
    current = load_bootstrap_review_context(PROJECT_ROOT)
    result = verify_development_transition(
        DevelopmentTransitionRequest(
            previous_step_id="METAENGINE-1-SLICE-3",
            previous_step_commit=receipt.completed_step_commit,
            next_step_id="METAENGINE-1-SLICE-4",
            current_context=current,
            receipt=receipt,
        )
    )
    assert result.allowed is True
    assert result.reason == "DEVELOPMENT_REVIEW_TRANSITION_ALLOWED"


def test_slice3_final_review_receipt_fails_closed_after_library_drift():
    receipt = _slice3_receipt()
    current = load_bootstrap_review_context(PROJECT_ROOT)
    stale = DevelopmentReviewContext(
        review_context_version=current.review_context_version,
        constitution=current.constitution,
        architecture_library=ContentSnapshot(
            current.architecture_library.snapshot_version,
            current.architecture_library.files,
            "f" * 64,
        ),
        policy=current.policy,
    )
    result = verify_development_transition(
        DevelopmentTransitionRequest(
            previous_step_id="METAENGINE-1-SLICE-3",
            previous_step_commit=receipt.completed_step_commit,
            next_step_id="METAENGINE-1-SLICE-4",
            current_context=stale,
            receipt=receipt,
        )
    )
    assert result.allowed is False
    assert result.reason == "DEVELOPMENT_REVIEW_LIBRARY_SNAPSHOT_STALE"
