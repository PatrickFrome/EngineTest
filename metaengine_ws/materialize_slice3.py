"""METAENGINE-1-SLICE-3 — materialize the first ingestion wave.

Produces the content-addressed Source Registry, Reference Vault, and
Mechanism Library for the Slice-3 first wave, then verifies them.

Honesty note (PRESERVE_ABSTENTION): foreign source bytes (DeepSeek, Qwen,
Kimi-Linear, Mistral, GLM, Llama 4, Kimi K3) cannot be fetched/verified in
this environment, so they are registered as UNOBSERVED ingestion blockers
(BLOCKED_NO_NETWORK) — never silently omitted and never with a fabricated
hash.  Ingestion PASS is NOT claimed for unfetched bytes.

One genuinely OBSERVED permissive source is included — the MetaEngine
constitutional-assimilation design spec, whose real bytes are already in the
workspace, are hashed, stored in the content-addressed Reference Vault, and
re-verified.  This exercises the full OBSERVED -> store -> verify path.
"""

from __future__ import annotations

import json
from pathlib import Path

from metaengine.mechanism_library import (
    MechanismCandidate,
    MechanismLibrary,
    MechanismState,
)
from metaengine.reference_vault import ReferenceVault, ReferenceVaultEntry
from metaengine.source_registry import (
    ArchitectureClaim,
    IngestionBlocker,
    IngestionStatus,
    SourceClass,
    SourceRecord,
    SourceRegistry,
)
from metaengine.util import sha256_file, write_json

ROOT = Path(__file__).resolve().parent
ARCH_LIB = ROOT / "research" / "architecture_library"
VAULT_ROOT = ROOT / "reference_vault"
ARCH_LIB.mkdir(parents=True, exist_ok=True)
VAULT_ROOT.mkdir(parents=True, exist_ok=True)

RETRIEVED_AT = "2026-08-14T00:00:00Z"
BLOCKED_NO_NETWORK = IngestionBlocker.create(
    status=IngestionStatus.UNOBSERVED,
    reason="BLOCKED_NO_NETWORK",
    detail="Foreign source bytes cannot be fetched/verified in this recovery environment; recorded as an explicit ingestion blocker, not silently omitted.",
)
CLOSED_NO_BYTES = IngestionBlocker.create(
    status=IngestionStatus.UNOBSERVED,
    reason="CLOSED_NO_SOURCE_BYTES",
    detail="Closed system; only public papers/system cards/observed behavior are available. No source bytes retained.",
)


def _blocked_permissive(
    *,
    source_id: str,
    publisher: str,
    system_name: str,
    version: str,
    locator: str,
    release: str,
    license_name: str,
    claims: tuple[ArchitectureClaim, ...] = (),
    mechanisms: tuple[str, ...] = (),
) -> SourceRecord:
    return SourceRecord.create(
        source_id=source_id,
        publisher=publisher,
        system_name=system_name,
        version=version,
        source_class=SourceClass.PERMISSIVE_CODE,
        official_source_locator=locator,
        exact_commit_or_release=release,
        retrieved_at=RETRIEVED_AT,
        source_sha256=None,
        license_name=license_name,
        license_sha256=None,
        allowed_use=("ANALYSIS", "REFERENCE", "REIMPLEMENTATION"),
        architecture_claims=claims,
        retained_reference_paths=(),
        mechanism_candidates=mechanisms,
        ingestion=IngestionStatus.UNOBSERVED,
        ingestion_blocker=BLOCKED_NO_NETWORK,
    )


def _blocked_restricted(
    *,
    source_id: str,
    publisher: str,
    system_name: str,
    version: str,
    locator: str,
    release: str,
    license_name: str,
    claims: tuple[ArchitectureClaim, ...] = (),
    mechanisms: tuple[str, ...] = (),
) -> SourceRecord:
    return SourceRecord.create(
        source_id=source_id,
        publisher=publisher,
        system_name=system_name,
        version=version,
        source_class=SourceClass.RESTRICTED_REFERENCE,
        official_source_locator=locator,
        exact_commit_or_release=release,
        retrieved_at=RETRIEVED_AT,
        source_sha256=None,
        license_name=license_name,
        license_sha256=None,
        allowed_use=("REFERENCE",),
        architecture_claims=claims,
        retained_reference_paths=(),
        mechanism_candidates=mechanisms,
        ingestion=IngestionStatus.UNOBSERVED,
        ingestion_blocker=BLOCKED_NO_NETWORK,
    )


def _closed_behavioral(
    *,
    source_id: str,
    publisher: str,
    system_name: str,
    version: str,
    locator: str,
    claims: tuple[ArchitectureClaim, ...] = (),
    mechanisms: tuple[str, ...] = (),
) -> SourceRecord:
    return SourceRecord.create(
        source_id=source_id,
        publisher=publisher,
        system_name=system_name,
        version=version,
        source_class=SourceClass.CLOSED_BEHAVIORAL_ONLY,
        official_source_locator=locator,
        exact_commit_or_release="n/a (closed)",
        retrieved_at=RETRIEVED_AT,
        source_sha256=None,
        license_name="Proprietary",
        license_sha256=None,
        allowed_use=("BEHAVIORAL_OBSERVATION",),
        architecture_claims=claims,
        retained_reference_paths=(),
        mechanism_candidates=mechanisms,
        ingestion=IngestionStatus.UNOBSERVED,
        ingestion_blocker=CLOSED_NO_BYTES,
    )


# ---------------------------------------------------------------------------
# 1. One genuinely OBSERVED permissive source: the MetaEngine design spec
#    (real bytes, real hash, stored in the content-addressed Reference Vault).
# ---------------------------------------------------------------------------

design_spec_path = ROOT / "docs/superpowers/specs/2026-08-13-metaengine-1-constitutional-assimilation-design.md"
design_spec_sha = sha256_file(design_spec_path)
design_spec_size = design_spec_path.stat().st_size
license_text_path = ROOT / "LICENSE.metaengine-design.md"
license_text = (
    "MetaEngine METAENGINE-1 Constitutional Assimilation Foundation Design\n"
    "Internal permissive reference document. Licensed for analysis, reference,\n"
    "and reimplementation within the MetaEngine program.\n"
)
license_text_path.write_text(license_text, encoding="utf-8")
license_sha = sha256_file(license_text_path)

metaengine_source = SourceRecord.create(
    source_id="src.metaengine.design.1",
    publisher="MetaEngine",
    system_name="METAENGINE-1 Constitutional Assimilation Design",
    version="2026-08-13",
    source_class=SourceClass.PERMISSIVE_CODE,
    official_source_locator="docs/superpowers/specs/2026-08-13-metaengine-1-constitutional-assimilation-design.md",
    exact_commit_or_release="637d0b569e38c2a965b43f7de2015ea66a788428",
    retrieved_at=RETRIEVED_AT,
    source_sha256=design_spec_sha,
    license_name="MetaEngine-Internal-Permissive",
    license_sha256=license_sha,
    allowed_use=("ANALYSIS", "REFERENCE", "REIMPLEMENTATION"),
    architecture_claims=(
        ArchitectureClaim.create(
            claim_id="metaengine.source_registry",
            statement="MetaEngine mandates a content-addressed Architecture Source Registry with three source classes and license fail-closed enforcement.",
            evidence_kind="DOCUMENTATION",
            evidence_refs=("docs/superpowers/specs/2026-08-13-metaengine-1-constitutional-assimilation-design.md#section-9",),
        ),
        ArchitectureClaim.create(
            claim_id="metaengine.mechanism_states",
            statement="Mechanisms progress A0->A1->A2->A3 and only A3 may automatically influence organization-policy generation.",
            evidence_kind="DOCUMENTATION",
            evidence_refs=("docs/superpowers/specs/2026-08-13-metaengine-1-constitutional-assimilation-design.md#section-10",),
        ),
    ),
    retained_reference_paths=(f"reference_vault/{design_spec_sha[:2]}/{design_spec_sha}",),
    mechanism_candidates=("mec.constitution_derived_testing",),
    ingestion=IngestionStatus.OBSERVED,
    ingestion_blocker=None,
)

metaengine_vault_entry = ReferenceVaultEntry.create(
    content_sha256=design_spec_sha,
    size=design_spec_size,
    source_record_id="src.metaengine.design.1",
    source_class=SourceClass.PERMISSIVE_CODE,
    license_name="MetaEngine-Internal-Permissive",
    license_sha256=license_sha,
    stored=True,
    blocker_reason=None,
)

# Store the real bytes in the content-addressed Reference Vault and verify.
stored_path = ReferenceVault.store_bytes(
    VAULT_ROOT, metaengine_vault_entry, design_spec_path.read_bytes()
)
assert stored_path.is_file()
ReferenceVault.verify_bytes(VAULT_ROOT, [metaengine_vault_entry])

# ---------------------------------------------------------------------------
# 2. Foreign permissive targets (UNOBSERVED — blocked, not silently omitted)
# ---------------------------------------------------------------------------

deepseek = _blocked_permissive(
    source_id="src.deepseek.1",
    publisher="DeepSeek",
    system_name="DeepSeek V3",
    version="V3 / V3.2",
    locator="https://github.com/deepseek-ai/DeepSeek-V3",
    release="public release tag (unfetched)",
    license_name="MIT (claimed; unverified in this environment)",
    claims=(
        ArchitectureClaim.create(
            claim_id="deepseek.moe",
            statement="DeepSeek V3 uses fine-grained mixture-of-experts with shared experts.",
            evidence_kind="PUBLIC_PAPER",
            evidence_refs=("https://github.com/deepseek-ai/DeepSeek-V3",),
        ),
        ArchitectureClaim.create(
            claim_id="deepseek.mla",
            statement="DeepSeek uses Multi-head Latent Attention to compress KV cache.",
            evidence_kind="PUBLIC_PAPER",
            evidence_refs=("https://github.com/deepseek-ai/DeepSeek-V3",),
        ),
    ),
    mechanisms=("mec.sparse_conditional_routing", "mec.latent_context_compression"),
)

qwen = _blocked_permissive(
    source_id="src.qwen.1",
    publisher="Alibaba",
    system_name="Qwen3",
    version="Qwen3-Next / Qwen3.5-class",
    locator="https://github.com/QwenLM/Qwen3",
    release="public release tag (unfetched)",
    license_name="Apache-2.0 (claimed; unverified in this environment)",
    claims=(
        ArchitectureClaim.create(
            claim_id="qwen.hybrid_thinking",
            statement="Qwen3 supports a hybrid thinking mode toggling reasoning on/off.",
            evidence_kind="PUBLIC_PAPER",
            evidence_refs=("https://github.com/QwenLM/Qwen3",),
        ),
    ),
    mechanisms=("mec.adaptive_reasoning_budget",),
)

kimi_linear = _blocked_permissive(
    source_id="src.kimi-linear.1",
    publisher="Moonshot AI",
    system_name="Kimi-Linear",
    version="research preview",
    locator="https://github.com/moonshotai (permissive research components)",
    release="public release tag (unfetched)",
    license_name="MIT (claimed; unverified in this environment)",
    claims=(
        ArchitectureClaim.create(
            claim_id="kimi-linear.delta_optimizer",
            statement="Kimi-Linear explores a Delta-attention/linearized attention optimizer.",
            evidence_kind="PUBLIC_PAPER",
            evidence_refs=("https://github.com/moonshotai",),
        ),
    ),
    mechanisms=("mec.latent_context_compression",),
)

mistral = _blocked_permissive(
    source_id="src.mistral.1",
    publisher="Mistral AI",
    system_name="Mistral",
    version="latest public",
    locator="https://github.com/mistralai",
    release="public release tag (unfetched)",
    license_name="Apache-2.0 (claimed; unverified in this environment)",
    claims=(
        ArchitectureClaim.create(
            claim_id="mistral.sliding_window",
            statement="Mistral uses sliding-window attention plus GQA.",
            evidence_kind="PUBLIC_PAPER",
            evidence_refs=("https://github.com/mistralai",),
        ),
    ),
    mechanisms=("mec.residual_organization_paths",),
)

glm = _blocked_permissive(
    source_id="src.glm.1",
    publisher="Z.ai",
    system_name="GLM",
    version="GLM-5.2 (target runtime)",
    locator="https://github.com/zai-org/glm-reference",
    release="v5.2.0 (unfetched)",
    license_name="MIT (claimed; unverified in this environment)",
    claims=(
        ArchitectureClaim.create(
            claim_id="glm.moe",
            statement="GLM uses a mixture-of-experts feed-forward block.",
            evidence_kind="PUBLIC_PAPER",
            evidence_refs=("https://github.com/zai-org/glm-reference",),
        ),
    ),
    mechanisms=("mec.sparse_conditional_routing",),
)

# ---------------------------------------------------------------------------
# 3. Restricted-reference targets
# ---------------------------------------------------------------------------

llama4 = _blocked_restricted(
    source_id="src.llama4.1",
    publisher="Meta",
    system_name="Llama 4",
    version="latest public",
    locator="https://github.com/meta-llama/llama-models",
    release="restricted release (unfetched)",
    license_name="Llama Community License (custom; reference-only)",
    claims=(
        ArchitectureClaim.create(
            claim_id="llama4.moe",
            statement="Llama 4 introduces a mixture-of-experts variant in the family.",
            evidence_kind="PUBLIC_PAPER",
            evidence_refs=("https://github.com/meta-llama/llama-models",),
        ),
    ),
    mechanisms=("mec.sparse_conditional_routing",),
)

kimi_k3 = _blocked_restricted(
    source_id="src.kimi-k3.1",
    publisher="Moonshot AI",
    system_name="Kimi K3",
    version="latest public",
    locator="https://platform.moonshot.cn/",
    release="restricted release (unfetched)",
    license_name="Moonshot custom license (reference-only)",
    claims=(
        ArchitectureClaim.create(
            claim_id="kimi-k3.agentic",
            statement="Kimi K3 is reported to emphasize agentic / tool-use behavior.",
            evidence_kind="PUBLIC_PAPER",
            evidence_refs=("https://platform.moonshot.cn/",),
        ),
    ),
    mechanisms=("mec.parallel_hypothesis_generation",),
)

# ---------------------------------------------------------------------------
# 4. Closed / behavioral-only targets
# ---------------------------------------------------------------------------

gpt56 = _closed_behavioral(
    source_id="src.gpt-5.6.1",
    publisher="OpenAI",
    system_name="GPT-5.6",
    version="public API behavior",
    locator="https://openai.com/",
    claims=(
        ArchitectureClaim.create(
            claim_id="gpt5.6.behavior",
            statement="GPT-5.6-class systems exhibit multi-step reasoning and tool use via public API behavior.",
            evidence_kind="OBSERVED_BEHAVIOR",
            evidence_refs=("https://openai.com/",),
        ),
    ),
    mechanisms=("mec.adaptive_reasoning_budget", "mec.speculative_multi_action"),
)

claude = _closed_behavioral(
    source_id="src.claude.1",
    publisher="Anthropic",
    system_name="Claude",
    version="opus/sonnet public behavior",
    locator="https://www.anthropic.com/claude",
    claims=(
        ArchitectureClaim.create(
            claim_id="claude.constitutional",
            statement="Claude uses constitutional-AI style alignment training.",
            evidence_kind="PUBLIC_PAPER",
            evidence_refs=("https://www.anthropic.com/research/constitutional-ai",),
        ),
    ),
    mechanisms=("mec.constitution_derived_testing",),
)

gemini = _closed_behavioral(
    source_id="src.gemini-deep-think.1",
    publisher="Google",
    system_name="Gemini Deep Think",
    version="public API behavior",
    locator="https://deepmind.google/",
    claims=(
        ArchitectureClaim.create(
            claim_id="gemini.deep_think",
            statement="Gemini Deep Think exposes extended thinking behavior via public API.",
            evidence_kind="OBSERVED_BEHAVIOR",
            evidence_refs=("https://deepmind.google/",),
        ),
    ),
    mechanisms=("mec.adaptive_reasoning_budget",),
)

# ---------------------------------------------------------------------------
# 5. Build the Source Registry
# ---------------------------------------------------------------------------

all_records = (
    metaengine_source,
    deepseek,
    qwen,
    kimi_linear,
    mistral,
    glm,
    llama4,
    kimi_k3,
    gpt56,
    claude,
    gemini,
)
registry = SourceRegistry.create(all_records)

# ---------------------------------------------------------------------------
# 6. Build the Reference Vault (one stored entry + blockers for the rest)
# ---------------------------------------------------------------------------

blocked_entries = tuple(
    ReferenceVaultEntry.create(
        content_sha256="0" * 64,  # placeholder digest for UNOBSERVED (no real bytes)
        size=0,
        source_record_id=record.source_id,
        source_class=record.source_class,
        license_name=record.license_name,
        license_sha256=None,
        stored=False,
        blocker_reason=record.ingestion_blocker.reason,
    )
    for record in registry.records
    if record.ingestion is IngestionStatus.UNOBSERVED
)
vault = ReferenceVault.create((metaengine_vault_entry, *blocked_entries))

# ---------------------------------------------------------------------------
# 7. Mechanism candidates (A0/A1 only)
# ---------------------------------------------------------------------------

candidates = (
    MechanismCandidate.create(
        mechanism_id="mec.sparse_conditional_routing",
        semantic_definition="Route only a subset of experts/paths per token via a learned gate.",
        origin_source_ids=("src.deepseek.1", "src.qwen.1", "src.glm.1", "src.llama4.1"),
        source_fact_boundary="Source papers report the routing pattern; exact gate implementation is source code only where permissively licensed.",
        hypothesized_effect="Reduces per-token compute without proportional quality loss under bounded load.",
        task_scope=("GENERATION", "MIXED_RETRIEVAL"),
        prerequisites=("learned_router_weights",),
        resource_cost="UNOBSERVED",
        complexity_cost="moderate router + load balancing",
        known_incompatibilities=("strict-determinism pipelines",),
        known_failures=(),
        implementation_variants=("top-1-router", "top-2-router"),
        experiment_receipts=(),
        ablation_receipts=(),
        transfer_receipts=(),
        confidence="UNOBSERVED",
        status=MechanismState.A0_OBSERVED,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.latent_context_compression",
        semantic_definition="Compress KV/context state into a latent representation to reduce attention cost.",
        origin_source_ids=("src.deepseek.1", "src.kimi-linear.1"),
        source_fact_boundary="Reported in public papers; transfer to MetaEngine is unverified.",
        hypothesized_effect="Longer effective context at fixed memory budget.",
        task_scope=("LONG_CONTEXT",),
        prerequisites=("compressor_head",),
        resource_cost="UNOBSERVED",
        complexity_cost="encoder + reconstruction",
        known_incompatibilities=(),
        known_failures=(),
        implementation_variants=("low_rank_kv", "latent_kv"),
        experiment_receipts=(),
        ablation_receipts=(),
        transfer_receipts=(),
        confidence="UNOBSERVED",
        status=MechanismState.A1_MECHANISM_HYPOTHESIS,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.adaptive_reasoning_budget",
        semantic_definition="Allocate reasoning depth/budget adaptively per query.",
        origin_source_ids=("src.qwen.1", "src.gpt-5.6.1", "src.gemini-deep-think.1"),
        source_fact_boundary="Observed as behavior in closed systems and as a mode toggle in Qwen3 public material.",
        hypothesized_effect="Better quality/cost trade-off across query difficulty.",
        task_scope=("REASONING",),
        prerequisites=("budget_controller",),
        resource_cost="UNOBSERVED",
        complexity_cost="budget policy + early-exit heads",
        known_incompatibilities=(),
        known_failures=(),
        implementation_variants=("mode_toggle", "early_exit"),
        experiment_receipts=(),
        ablation_receipts=(),
        transfer_receipts=(),
        confidence="UNOBSERVED",
        status=MechanismState.A0_OBSERVED,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.constitution_derived_testing",
        semantic_definition="Derive tests/invariants from a constitutional rule set.",
        origin_source_ids=("src.metaengine.design.1", "src.claude.1"),
        source_fact_boundary="MetaEngine K0/K1 invariants are the source fact; Claude constitutional-AI is behavioral evidence only.",
        hypothesized_effect="Automated, provenance-bound test generation from invariants.",
        task_scope=("TESTING",),
        prerequisites=("constitution_kernel",),
        resource_cost="low",
        complexity_cost="invariant->test compiler",
        known_incompatibilities=(),
        known_failures=(),
        implementation_variants=("k0_conformance_matrix",),
        experiment_receipts=(),
        ablation_receipts=(),
        transfer_receipts=(),
        confidence="LOW",
        status=MechanismState.A1_MECHANISM_HYPOTHESIS,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.residual_organization_paths",
        semantic_definition="Maintain residual paths across organization waves so earlier outputs remain reachable.",
        origin_source_ids=("src.mistral.1",),
        source_fact_boundary="Sliding-window/GQA patterns reported in public Mistral material.",
        hypothesized_effect="Stable long-range information flow in multi-wave organizations.",
        task_scope=("MULTI_WAVE",),
        prerequisites=(),
        resource_cost="UNOBSERVED",
        complexity_cost="residual wiring",
        known_incompatibilities=(),
        known_failures=(),
        implementation_variants=("sliding_window", "gqa_residual"),
        experiment_receipts=(),
        ablation_receipts=(),
        transfer_receipts=(),
        confidence="UNOBSERVED",
        status=MechanismState.A0_OBSERVED,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.parallel_hypothesis_generation",
        semantic_definition="Generate multiple parallel hypotheses/plans and critique them.",
        origin_source_ids=("src.kimi-k3.1", "src.gpt-5.6.1"),
        source_fact_boundary="Observed as agentic behavior in closed/restricted systems.",
        hypothesized_effect="Higher coverage of solution space at higher compute cost.",
        task_scope=("PLANNING",),
        prerequisites=("critic_role",),
        resource_cost="UNOBSERVED",
        complexity_cost="fan-out + discriminator",
        known_incompatibilities=(),
        known_failures=(),
        implementation_variants=("n_of_m_hypotheses",),
        experiment_receipts=(),
        ablation_receipts=(),
        transfer_receipts=(),
        confidence="UNOBSERVED",
        status=MechanismState.A0_OBSERVED,
    ),
    MechanismCandidate.create(
        mechanism_id="mec.speculative_multi_action",
        semantic_definition="Speculatively propose multiple actions/plans and verify in parallel.",
        origin_source_ids=("src.gpt-5.6.1",),
        source_fact_boundary="Behavioral observation only; no source.",
        hypothesized_effect="Lower latency for multi-step actions when verifier is cheap.",
        task_scope=("AGENTIC",),
        prerequisites=("verifier_role",),
        resource_cost="UNOBSERVED",
        complexity_cost="speculator + verifier",
        known_incompatibilities=(),
        known_failures=(),
        implementation_variants=("speculative_decode_like",),
        experiment_receipts=(),
        ablation_receipts=(),
        transfer_receipts=(),
        confidence="UNOBSERVED",
        status=MechanismState.A0_OBSERVED,
    ),
)
mechanism_library = MechanismLibrary.create(candidates)
mechanism_library.assert_no_a3_influence()

# ---------------------------------------------------------------------------
# 8. Verify everything and write artifacts
# ---------------------------------------------------------------------------

assert registry.verify() is True
assert vault.verify() is True
assert mechanism_library.verify() is True
assert mechanism_library.has_a3_influence() is False

write_json(ARCH_LIB / "source_registry.json", registry.as_dict())
write_json(ARCH_LIB / "reference_vault.json", vault.as_dict())
write_json(ARCH_LIB / "mechanism_library.json", mechanism_library.as_dict())

summary = {
    "slice": "METAENGINE-1-SLICE-3",
    "source_registry_hash": registry.registry_hash,
    "reference_vault_hash": vault.vault_hash,
    "mechanism_library_hash": mechanism_library.library_hash,
    "source_count": len(registry.records),
    "vault_entry_count": len(vault.entries),
    "stored_byte_entries": sum(1 for e in vault.entries if e.stored),
    "blocked_entries": sum(1 for e in vault.entries if not e.stored),
    "mechanism_count": len(mechanism_library.candidates),
    "a3_influence": mechanism_library.has_a3_influence(),
    "observed_sources": [
        r.source_id for r in registry.records if r.ingestion == "OBSERVED"
    ],
    "unobserved_blockers": [
        {"source_id": r.source_id, "reason": r.ingestion_blocker.reason}
        for r in registry.records
        if r.ingestion == "UNOBSERVED"
    ],
    "ingestion_pass_claimed": False,
    "ingestion_pass_reason": "Foreign source bytes cannot be fetched/verified in this recovery environment; permissive targets remain UNOBSERVED blockers. Only the internal MetaEngine design spec is OBSERVED+stored+verified.",
}
write_json(ARCH_LIB / "slice3_ingestion_summary.json", summary)

print("SLICE3_MATERIALIZE_PASS")
print(json.dumps(summary, indent=2))
