from __future__ import annotations

import json
from pathlib import Path

from metaengine.devfabric.federation.types import SLOT_ORDER, SlotId

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_federation_defines_exactly_eight_ordered_slots():
    assert SLOT_ORDER == tuple(SlotId(f"C{i}") for i in range(8))
    assert len(set(SLOT_ORDER)) == 8


def test_role_catalog_maps_exactly_the_eight_semantic_roles():
    catalog = json.loads((PROJECT_ROOT / "chat_federation" / "ROLE_CATALOG.json").read_text(encoding="utf-8"))
    assert catalog == {
        "C0": "SYNCHRONIZER_INTEGRATOR",
        "C1": "ARCHITECTURE",
        "C2": "CORE_ENGINE",
        "C3": "AI_SWARM",
        "C4": "EDGE_MCP",
        "C5": "DATA_SERVICES",
        "C6": "VERIFICATION_SECURITY",
        "C7": "RESEARCH_BENCHMARK",
    }

import pytest

from metaengine.devfabric.federation.roles import load_role_genome
from metaengine.devfabric.models import PrivacyClass


def test_soft_update_cannot_change_hard_authority():
    genome = load_role_genome(PROJECT_ROOT, SlotId.C6)
    updated = genome.with_soft_update({"capability_weights": {"security": 0.95}})
    assert updated.hard == genome.hard
    assert updated.profile_hash != genome.profile_hash


def test_all_role_genomes_match_slot_and_hard_role_matrix():
    expected = {
        SlotId.C0: ("SYNCHRONIZER_INTEGRATOR", PrivacyClass.P2),
        SlotId.C1: ("ARCHITECTURE", PrivacyClass.P2),
        SlotId.C2: ("CORE_ENGINE", PrivacyClass.P3),
        SlotId.C3: ("AI_SWARM", PrivacyClass.P3),
        SlotId.C4: ("EDGE_MCP", PrivacyClass.P2),
        SlotId.C5: ("DATA_SERVICES", PrivacyClass.P2),
        SlotId.C6: ("VERIFICATION_SECURITY", PrivacyClass.P3),
        SlotId.C7: ("RESEARCH_BENCHMARK", PrivacyClass.P2),
    }
    for slot, (role, privacy_ceiling) in expected.items():
        genome = load_role_genome(PROJECT_ROOT, slot)
        assert genome.hard.slot is slot
        assert genome.hard.role == role
        assert genome.hard.privacy_ceiling is privacy_ceiling
        assert "CANONICAL_BYPASS" in genome.hard.prohibited_actions
        assert "SECRET_RETRIEVAL" in genome.hard.prohibited_actions
        assert len(genome.profile_hash) == 64


def test_role_genome_rejects_out_of_bounds_soft_values():
    genome = load_role_genome(PROJECT_ROOT, SlotId.C3)
    with pytest.raises(ValueError, match="capability weight"):
        genome.with_soft_update({"capability_weights": {"coding": 1.01}})
    with pytest.raises(ValueError, match="exploration_weight"):
        genome.with_soft_update({"exploration_weight": 0.26})
    with pytest.raises(ValueError, match="concurrency_preference"):
        genome.with_soft_update({"concurrency_preference": 7})


def test_role_genome_loader_rejects_filename_slot_mismatch(tmp_path):
    role_dir = tmp_path / "chat_federation" / "ROLE_GENOMES"
    role_dir.mkdir(parents=True)
    source = json.loads((PROJECT_ROOT / "chat_federation" / "ROLE_GENOMES" / "C0.json").read_text(encoding="utf-8")) if (PROJECT_ROOT / "chat_federation" / "ROLE_GENOMES" / "C0.json").exists() else {
        "version": "d6-role-v1",
        "hard": {
            "slot": "C1",
            "role": "ARCHITECTURE",
            "authority_boundaries": [],
            "prohibited_actions": ["CANONICAL_BYPASS", "SECRET_RETRIEVAL"],
            "subsystem_ownership": [],
            "privacy_ceiling": "P2",
            "mandatory_reviewers": ["C6"],
            "allowed_integration_modes": ["EXCLUSIVE"]
        },
        "soft": {
            "capability_weights": {"architecture": 0.8},
            "preferred_workers": [],
            "preferred_task_classes": [],
            "review_pairings": ["C6"],
            "exploration_weight": 0.1,
            "concurrency_preference": 2,
            "provider_priors": {}
        }
    }
    source["hard"]["slot"] = "C1"
    (role_dir / "C0.json").write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ValueError, match="filename slot"):
        load_role_genome(tmp_path, SlotId.C0)


def test_role_genome_json_contains_no_runtime_or_secret_fields():
    forbidden_fragments = ("secret", "token", "session", "lease", "credential", "password")

    def collect_keys(value):
        if isinstance(value, dict):
            for key, item in value.items():
                yield str(key).lower()
                yield from collect_keys(item)
        elif isinstance(value, list):
            for item in value:
                yield from collect_keys(item)

    for slot in SLOT_ORDER:
        payload = json.loads((PROJECT_ROOT / "chat_federation" / "ROLE_GENOMES" / f"{slot.value}.json").read_text(encoding="utf-8"))
        keys = tuple(collect_keys(payload))
        assert not any(fragment in key for key in keys for fragment in forbidden_fragments)

from metaengine.devfabric.codec import canonical_digest


def test_soft_update_accepts_slot_enums_and_profile_hash_is_canonical():
    genome = load_role_genome(PROJECT_ROOT, SlotId.C3)
    updated = genome.with_soft_update({"review_pairings": (SlotId.C6, SlotId.C7)})
    assert updated.soft.review_pairings == (SlotId.C6, SlotId.C7)
    assert updated.profile_hash == canonical_digest(
        {"version": updated.version, "hard": updated.hard, "soft": updated.soft}
    )
