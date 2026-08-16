"""METAENGINE-1-SLICE-3 — generate the post-step DevelopmentEvolutionReviewReceipt.

Builds the content-addressed review receipt for the completed Slice-3 step
using the official ``DevelopmentEvolutionReviewReceipt`` API, verifies its
integrity, and writes it to ``03_EVIDENCE/METAENGINE1/``.

The receipt is the mandatory gate: no next step is admitted without it and
matching current snapshots.
"""

from __future__ import annotations

import json
from pathlib import Path

from metaengine.devfabric.development_review import (
    DevelopmentAlternative,
    DevelopmentAlternativeKind,
    DevelopmentEvolutionReviewReceipt,
    DevelopmentReviewDecision,
    load_bootstrap_review_context,
    verify_receipt_integrity,
)
from metaengine.util import sha256_file, write_json

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "03_EVIDENCE" / "METAENGINE1"

# --- Freshly recomputed current snapshots (must match the Slice-2 receipt) ---
ctx = load_bootstrap_review_context(ROOT)
constitution_hash = ctx.constitution.snapshot_hash
architecture_library_snapshot_hash = ctx.architecture_library.snapshot_hash
policy_snapshot_hash = ctx.policy.snapshot_hash

assert constitution_hash == "bbcdd652e97d2ab4136f00d655baf458eaeb1182cc30adacd07568095e40f28a"
assert architecture_library_snapshot_hash == "d5b32e0a8b9983cd36faed2cf105ecf3670cf9490578f0d939cbbdf4b1103445"
assert policy_snapshot_hash == "1888a575abae2ba844f53a005a23c48ed5581722d2a64cf6df40f60bbda66f32"

# --- Evidence hashes for the completed Slice-3 step ---
summary = json.loads((ROOT / "research/architecture_library/slice3_ingestion_summary.json").read_text())
evidence_hashes = [
    summary["source_registry_hash"],
    summary["reference_vault_hash"],
    summary["mechanism_library_hash"],
    sha256_file(ROOT / "metaengine/source_registry.py"),
    sha256_file(ROOT / "metaengine/reference_vault.py"),
    sha256_file(ROOT / "metaengine/mechanism_library.py"),
    sha256_file(ROOT / "tests/test_source_registry.py"),
    sha256_file(ROOT / "tests/test_reference_vault.py"),
    sha256_file(ROOT / "tests/test_mechanism_library.py"),
    sha256_file(ROOT / "03_EVIDENCE/METAENGINE1/metaengine-1-slice-3-pre-step-review.json"),
]

relevant_mechanism_ids = [
    "ARCHITECTURE_SOURCE_REGISTRY_V1",
    "REFERENCE_VAULT_V1",
    "MECHANISM_LIBRARY_A0A1",
    "LOSS_AWARE_LEGACY_ADAPTER",
    "ORGANIZATION_POLICY_V1",
    "RESOURCE_DESCRIPTOR_V1",
    "UNOBSERVED_MEASUREMENT_SEMANTICS",
]

alternatives = (
    DevelopmentAlternative.create(
        kind=DevelopmentAlternativeKind.CURRENT,
        summary="No Source Registry / Reference Vault exists (Slice-2 status quo); cannot satisfy the Slice-3 objective or program success criteria #6/#7/#8/#9.",
        evidence_hashes=evidence_hashes,
    ),
    DevelopmentAlternative.create(
        kind=DevelopmentAlternativeKind.MINIMAL,
        summary="Flat JSON list of {publisher,version,url} with no content hashing, no license/source-class enforcement, no vault; loses provenance integrity, UNOBSERVED semantics, and fail-closed enforcement. Violates PROVENANCE_PRIMARY_EVIDENCE and PRIVACY_PERMISSION_FAIL_CLOSED.",
        evidence_hashes=evidence_hashes,
    ),
    DevelopmentAlternative.create(
        kind=DevelopmentAlternativeKind.LIBRARY,
        summary="Vendor upstream repositories as git submodules/copied trees inside metaengine/ Core; provides real bytes but imports mutable foreign repositories into Core and creates direct runtime dependencies on foreign code, violating 'Do not vendor mutable upstream repositories into MetaEngine Core'.",
        evidence_hashes=evidence_hashes,
    ),
    DevelopmentAlternative.create(
        kind=DevelopmentAlternativeKind.SYNTHESIS,
        summary="Typed content-addressed Source Registry (SourceRecord frozen dataclass following the ResourceDescriptor pattern) with mandatory license/source-class fail-closed enforcement; separate content-addressed Reference Vault holding foreign bytes OUTSIDE Core/CONTROL; Mechanism Library recording A0/A1 candidates only. Blocked downloads recorded as explicit UNOBSERVED ingestion blockers, never silently omitted. Selected.",
        evidence_hashes=evidence_hashes,
    ),
)

receipt = DevelopmentEvolutionReviewReceipt.create(
    completed_step_id="METAENGINE-1-SLICE-3",
    completed_step_commit="637d0b569e38c2a965b43f7de2015ea66a788428",
    completed_step_evidence_hashes=evidence_hashes,
    constitution_hash=constitution_hash,
    architecture_library_snapshot_hash=architecture_library_snapshot_hash,
    policy_snapshot_hash=policy_snapshot_hash,
    relevant_mechanism_ids=relevant_mechanism_ids,
    alternatives_considered=alternatives,
    decision=DevelopmentReviewDecision.ACCEPT_WITH_FOLLOWUP_EXPERIMENT,
    rationale=(
        "Slice 3 implements a reproducible, content-addressed Architecture Source Registry and "
        "Reference Vault following the ResourceDescriptor/OrganizationPolicy pattern from Slice 2. "
        "License/source-class enforcement fails closed (CLOSED_BEHAVIORAL_ONLY may not retain bytes; "
        "PERMISSIVE_CODE retention requires a verified license_sha256). UNOBSERVED ingestion blockers "
        "preserve abstention: foreign source bytes that cannot be fetched/verified in this recovery "
        "environment are recorded as explicit blockers, never silently omitted or fabricated. The "
        "constitution/architecture-library/policy snapshot hashes are unchanged from the Slice-2 recert "
        "receipt, confirming Slice 3 does not amend the constitutional kernel, architecture library, or "
        "active policy. Canonical checkpoint, champion policy, promotion state, and D6-G1 adaptation "
        "state are untouched. The decision is ACCEPT_WITH_FOLLOWUP_EXPERIMENT because the success "
        "criterion 'at least the first permissive source pack is actually ingested and verified before "
        "claiming ingestion PASS' is honestly NOT yet satisfied for the foreign permissive targets "
        "(DeepSeek/Qwen/Kimi-Linear/Mistral/GLM): their bytes are UNOBSERVED blockers. Only the internal "
        "MetaEngine design spec is OBSERVED, stored in the content-addressed vault, and re-verified."
    ),
    complexity_delta=(
        "Small bounded Core surface: three new modules (source_registry, reference_vault, "
        "mechanism_library), three schemas, three test modules (50 tests). No new service, database "
        "authority, transport, model dependency, or Core runtime dependency on foreign code. Foreign "
        "source bytes live outside metaengine/ Core and outside the CONTROL capsule."
    ),
    capability_hypothesis=(
        "A content-addressed, license-fail-closed source registry lets MetaEngine pin and classify "
        "external architecture sources as research material without vendoring foreign code into Core, "
        "enabling honest, provenance-bound mechanism candidate recording (A0/A1) for later "
        "evidence-gated assimilation."
    ),
    required_followup_experiment=(
        "When a network-capable environment is available, fetch and hash-verify the permissive foreign "
        "source packs (DeepSeek, Qwen, Kimi-Linear, Mistral, GLM), store their bytes in the "
        "content-addressed Reference Vault, and transition their ingestion from UNOBSERVED-blocker to "
        "OBSERVED. Only then may ingestion PASS be claimed for those sources. Mechanism candidates may "
        "advance from A0/A1 toward A2 only via independent MetaEngine implementation + ablation/transfer "
        "receipts; A3 remains out of scope for Slice 3."
    ),
    constitutional_findings=(
        "PROVENANCE_PRIMARY_EVIDENCE: every SourceRecord pins exact upstream release/commit and content hash; derived notes never replace pinned source bytes as primary evidence.",
        "PRESERVE_ABSTENTION: blocked downloads are recorded as explicit UNOBSERVED ingestion blockers with a reason; never silently converted to a zero-byte success or a fabricated hash (ingestion_pass_claimed=false).",
        "MUTATION_REQUIRES_RECEIPT: SourceRecord/ReferenceVaultEntry/MechanismCandidate are content-addressed; from_dict re-verifies the claimed hash; the registry/vault/library expose aggregate hashes and verify().",
        "NO_EXECUTABLE_SELF_MODIFICATION: the Reference Vault stores foreign bytes as inert content-addressed blobs; Slice 3 never executes them.",
        "PRIVACY_PERMISSION_FAIL_CLOSED: no source enters the library without an explicit source_class and license_name; CLOSED_BEHAVIORAL_ONLY may not retain source bytes; PERMISSIVE_CODE retention requires a verified license_sha256.",
        "SEPARATE_GENERATION_AND_PROMOTION: mechanism candidates are recorded at A0/A1 only; A2/A3 are rejected at creation time; assert_no_a3_influence() guards that the library exerts no automatic influence on organization-policy generation.",
    ),
    library_findings=(
        "Spec section 9 (Architecture Source Registry) is implemented: three mandatory source classes, the 15-field source record, and the reference-vault boundary (research/architecture_library/ tracked metadata + reference_vault/ content-addressed bytes).",
        "Spec section 10 (Mechanism Library) is implemented for A0/A1: the four-state enum is present but Slice 3 admits A0/A1 only; only A3 may automatically influence generation, and the library asserts none exists.",
        "The Slice-2 ResourceDescriptor pattern (frozen dataclass + create()/payload()/hash via canonical_hash + from_dict claimed-hash re-verification) is reused for SourceRecord, ReferenceVaultEntry, and MechanismCandidate, keeping the Core IR consistent.",
        "Existing MetaEngine architectural influences are registered without duplicate implementation: the MetaEngine constitutional-assimilation design spec is the one OBSERVED permissive source (real bytes, hash-verified, stored in the vault).",
    ),
    policy_findings=(
        "Canonical checkpoint metaengine-chat-2.3.0-alpha.1-cp001 remains VERIFIED_CURRENT; active policy 1868b3c7... remains ACTIVE generation 2 with self_modifying_code_allowed=false; canonical adaptation receipts remain 0; finalized epochs remain 1; release promotion remains BLOCKED; D6-G1 remains shadow-only. None of these were mutated by Slice 3.",
        "constitution_snapshot_hash, architecture_library_snapshot_hash, and policy_snapshot_hash are unchanged from the Slice-2 recert receipt, confirming Slice 3 does not amend the constitutional kernel, architecture library, or active policy.",
        "The 18-tool chat-facing Federation MCP allowlist is unchanged; Slice 3 adds no chat-facing tools.",
        "Slice 3 is limited to source/reference registry and mechanism candidates; no foreign code becomes a Core runtime dependency merely by ingestion, and no mechanism is auto-promoted.",
    ),
)

# --- Verify integrity and write ---
verification = verify_receipt_integrity(receipt)
assert verification.valid, verification.reason

write_json(EVIDENCE / "metaengine-1-slice-3-development-review-receipt.json", receipt.as_dict())

# Also write a transition record (Slice 3 -> Slice 4) once Slice 4 is defined;
# for now record the receipt + verification.
transition = {
    "review_protocol_version": receipt.review_protocol_version,
    "completed_step_id": receipt.completed_step_id,
    "completed_step_commit": receipt.completed_step_commit,
    "receipt_hash": receipt.receipt_hash,
    "decision": receipt.decision.value,
    "next_step_allowed": receipt.next_step_allowed,
    "verification": {"valid": verification.valid, "reason": verification.reason},
    "constitution_snapshot_hash": constitution_hash,
    "architecture_library_snapshot_hash": architecture_library_snapshot_hash,
    "policy_snapshot_hash": policy_snapshot_hash,
    "snapshot_hashes_match_slice2_receipt": (
        constitution_hash == "bbcdd652e97d2ab4136f00d655baf458eaeb1182cc30adacd07568095e40f28a"
        and architecture_library_snapshot_hash == "d5b32e0a8b9983cd36faed2cf105ecf3670cf9490578f0d939cbbdf4b1103445"
        and policy_snapshot_hash == "1888a575abae2ba844f53a005a23c48ed5581722d2a64cf6df40f60bbda66f32"
    ),
    "note": "Slice 3->4 transition is not yet requested; this record documents the Slice-3 receipt and that canonical state is unchanged. A separate authorized gate is required before any canonical checkpoint/champion/promotion/D6-G1 mutation.",
}
write_json(EVIDENCE / "slice3_completion_record.json", transition)

print("SLICE3_RECEIPT_PASS")
print("receipt_hash         :", receipt.receipt_hash)
print("decision             :", receipt.decision.value)
print("next_step_allowed    :", receipt.next_step_allowed)
print("verification         :", verification.valid, verification.reason)
print("snapshots_match_s2   :", transition["snapshot_hashes_match_slice2_receipt"])
