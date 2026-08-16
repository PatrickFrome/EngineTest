"""METAENGINE Phase 13 — Architecture Search Generator + Curriculum + Causal Attribution + Recursive Self-Improvement tests."""

from __future__ import annotations

import pytest

from metaengine.architecture_search import (
    ArchitectureSearchGenerator,
    ArchitectureCandidate,
    CandidateOrigin,
    SEARCH_GENERATOR_VERSION,
)


# ---------------------------------------------------------------------------
# Architecture Search Generator
# ---------------------------------------------------------------------------


class TestArchitectureSearchGenerator:
    def test_generates_candidates(self):
        gen = ArchitectureSearchGenerator(seed=42)
        candidates = gen.generate(mechanism_ids=["mec.a", "mec.b", "mec.c", "mec.d"], max_candidates=6)
        assert len(candidates) > 0
        assert all(isinstance(c, ArchitectureCandidate) for c in candidates)

    def test_candidates_have_hashes(self):
        gen = ArchitectureSearchGenerator(seed=42)
        candidates = gen.generate(mechanism_ids=["mec.a", "mec.b"], max_candidates=4)
        for c in candidates:
            assert len(c.candidate_hash) == 64

    def test_deterministic_with_same_seed(self):
        gen1 = ArchitectureSearchGenerator(seed=42)
        gen2 = ArchitectureSearchGenerator(seed=42)
        c1 = gen1.generate(mechanism_ids=["mec.a", "mec.b", "mec.c"], max_candidates=4)
        c2 = gen2.generate(mechanism_ids=["mec.a", "mec.b", "mec.c"], max_candidates=4)
        assert len(c1) == len(c2)
        assert c1[0].candidate_hash == c2[0].candidate_hash

    def test_biography_guided_candidate(self):
        gen = ArchitectureSearchGenerator(seed=42)
        candidates = gen.generate(
            mechanism_ids=["mec.a", "mec.b", "mec.c"],
            biography_priors={"mec.a": 0.9, "mec.b": 0.8, "mec.c": 0.3},
            max_candidates=6,
        )
        bio = [c for c in candidates if c.origin == CandidateOrigin.BIOGRAPHY_GUIDED]
        assert len(bio) >= 1
        assert "mec.a" in bio[0].mechanism_ids  # highest prior

    def test_novelty_candidates_explore_unexplored(self):
        gen = ArchitectureSearchGenerator(seed=99)
        candidates = gen.generate(
            mechanism_ids=["mec.a", "mec.b", "mec.c", "mec.d"],
            champion_mechanisms=["mec.a", "mec.b"],
            max_candidates=10,
        )
        novel = [c for c in candidates if c.origin == CandidateOrigin.NOVELTY]
        for c in novel:
            assert c.novelty_score >= 0.5

    def test_adversarial_candidate_uses_non_champion(self):
        gen = ArchitectureSearchGenerator(seed=42)
        candidates = gen.generate(
            mechanism_ids=["mec.a", "mec.b", "mec.c", "mec.d"],
            champion_mechanisms=["mec.a", "mec.b"],
            max_candidates=10,
        )
        advers = [c for c in candidates if c.origin == CandidateOrigin.ADVERSARIAL]
        assert len(advers) >= 1
        for c in advers:
            assert "mec.a" not in c.mechanism_ids
            assert "mec.b" not in c.mechanism_ids

    def test_dominated_configs_avoided(self):
        gen = ArchitectureSearchGenerator(seed=42)
        dominated = [("mec.a", "mec.b")]
        candidates = gen.generate(
            mechanism_ids=["mec.a", "mec.b", "mec.c"],
            dominated_configs=dominated,
            max_candidates=10,
        )
        for c in candidates:
            if c.origin == CandidateOrigin.RECOMBINATION:
                assert tuple(sorted(c.mechanism_ids)) not in [tuple(sorted(d)) for d in dominated]

    def test_candidates_sorted_by_novelty(self):
        gen = ArchitectureSearchGenerator(seed=42)
        candidates = gen.generate(mechanism_ids=["mec.a", "mec.b", "mec.c", "mec.d"], max_candidates=8)
        novelties = [c.novelty_score for c in candidates]
        assert novelties == sorted(novelties, reverse=True)

    def test_truth_effect_none(self):
        gen = ArchitectureSearchGenerator(seed=42)
        candidates = gen.generate(mechanism_ids=["mec.a"], max_candidates=2)
        for c in candidates:
            assert c.payload()["truth_effect"] == "NONE"

    def test_candidate_hash_deterministic(self):
        gen = ArchitectureSearchGenerator(seed=42)
        c1 = gen.generate(mechanism_ids=["mec.a", "mec.b"], max_candidates=1)
        c2 = gen.generate(mechanism_ids=["mec.a", "mec.b"], max_candidates=1)
        # Same seed + same input → same first candidate
        if len(c1) > 0 and len(c2) > 0:
            assert c1[0].candidate_hash == c2[0].candidate_hash

    def test_max_candidates_respected(self):
        gen = ArchitectureSearchGenerator(seed=42)
        candidates = gen.generate(mechanism_ids=["mec.a", "mec.b", "mec.c", "mec.d"], max_candidates=3)
        assert len(candidates) <= 3

    def test_empty_mechanisms_uses_default(self):
        gen = ArchitectureSearchGenerator(seed=42)
        candidates = gen.generate(max_candidates=2)
        assert len(candidates) > 0

    def test_generator_version(self):
        assert SEARCH_GENERATOR_VERSION == "METAENGINE-ARCHITECTURE-SEARCH-1"

    def test_candidate_serializable(self):
        gen = ArchitectureSearchGenerator(seed=42)
        candidates = gen.generate(mechanism_ids=["mec.a", "mec.b"], max_candidates=2)
        for c in candidates:
            d = c.payload()
            assert "candidate_id" in d
            assert "origin" in d
            assert "mechanism_ids" in d
            assert "novelty_score" in d


# ---------------------------------------------------------------------------
# Phase 14: Curriculum / Task Generator
# ---------------------------------------------------------------------------


class TestCurriculumGenerator:
    def test_curriculum_generator_exists(self):
        from metaengine.curriculum_generator import CurriculumGenerator
        assert CurriculumGenerator is not None

    def test_generates_tasks(self):
        from metaengine.curriculum_generator import CurriculumGenerator
        gen = CurriculumGenerator(seed=42)
        tasks = gen.generate(count=5)
        assert len(tasks) == 5

    def test_tasks_have_difficulty(self):
        from metaengine.curriculum_generator import CurriculumGenerator, DifficultyLevel
        gen = CurriculumGenerator(seed=42)
        tasks = gen.generate(count=5)
        for t in tasks:
            assert t.difficulty in DifficultyLevel

    def test_curriculum_progressive_difficulty(self):
        from metaengine.curriculum_generator import CurriculumGenerator
        gen = CurriculumGenerator(seed=42)
        tasks = gen.generate(count=10, progressive=True)
        difficulties = [t.difficulty.value for t in tasks]
        # Progressive: EASY < MEDIUM < HARD < ADVERSARIAL
        order = {'EASY': 0, 'MEDIUM': 1, 'HARD': 2, 'ADVERSARIAL': 3}
        indices = [order[d] for d in difficulties]
        assert indices == sorted(indices)

    def test_tasks_are_discriminative(self):
        from metaengine.curriculum_generator import CurriculumGenerator
        gen = CurriculumGenerator(seed=42)
        tasks = gen.generate(count=5)
        # Each task must have a source_text that could discriminate between architectures
        for t in tasks:
            assert len(t.source_text) > 20
            assert t.capability_targets  # non-empty

    def test_task_hash_deterministic(self):
        from metaengine.curriculum_generator import CurriculumGenerator
        gen1 = CurriculumGenerator(seed=42)
        gen2 = CurriculumGenerator(seed=42)
        t1 = gen1.generate(count=1)
        t2 = gen2.generate(count=1)
        assert t1[0].task_hash == t2[0].task_hash


# ---------------------------------------------------------------------------
# Phase 15: Causal Attribution Engine
# ---------------------------------------------------------------------------


class TestCausalAttribution:
    def test_causal_engine_exists(self):
        from metaengine.causal_attribution import CausalAttributionEngine
        assert CausalAttributionEngine is not None

    def test_attributes_cause(self):
        from metaengine.causal_attribution import CausalAttributionEngine, CausalFinding
        engine = CausalAttributionEngine()
        finding = engine.attribute(
            winner_policy="P0",
            loser_policy="P1",
            ablated_component="routing",
            quality_with=0.9,
            quality_without=0.5,
        )
        assert isinstance(finding, CausalFinding)
        assert finding.component == "routing"
        assert finding.effect_size > 0
        assert finding.confidence > 0

    def test_causal_finding_hash(self):
        from metaengine.causal_attribution import CausalAttributionEngine
        engine = CausalAttributionEngine()
        f1 = engine.attribute(winner_policy="P0", loser_policy="P1", ablated_component="routing", quality_with=0.9, quality_without=0.5)
        f2 = engine.attribute(winner_policy="P0", loser_policy="P1", ablated_component="routing", quality_with=0.9, quality_without=0.5)
        assert f1.finding_hash == f2.finding_hash

    def test_no_effect_when_equal(self):
        from metaengine.causal_attribution import CausalAttributionEngine
        engine = CausalAttributionEngine()
        finding = engine.attribute(winner_policy="P0", loser_policy="P1", ablated_component="routing", quality_with=0.8, quality_without=0.8)
        assert finding.effect_size == 0.0
        assert finding.confidence == 0.0

    def test_truth_effect_none(self):
        from metaengine.causal_attribution import CausalAttributionEngine
        engine = CausalAttributionEngine()
        finding = engine.attribute(winner_policy="P0", loser_policy="P1", ablated_component="routing", quality_with=0.9, quality_without=0.5)
        d = finding.payload()
        assert d["truth_effect"] == "NONE"


# ---------------------------------------------------------------------------
# Phase 16: Recursive Self-Improvement Measurement
# ---------------------------------------------------------------------------


class TestRecursiveSelfImprovement:
    def test_generation_comparator_exists(self):
        from metaengine.recursive_improvement import GenerationComparator
        assert GenerationComparator is not None

    def test_compares_generations(self):
        from metaengine.recursive_improvement import GenerationComparator, GenerationResult
        comp = GenerationComparator()
        result = comp.compare(
            g0_experiments=10,
            g0_correct_predictions=4,
            g1_experiments=6,
            g1_correct_predictions=5,
        )
        assert isinstance(result, GenerationResult)
        assert result.g1_better is True
        assert result.improvement_ratio > 1.0

    def test_g0_better_than_g1(self):
        from metaengine.recursive_improvement import GenerationComparator
        comp = GenerationComparator()
        result = comp.compare(
            g0_experiments=10,
            g0_correct_predictions=8,
            g1_experiments=10,
            g1_correct_predictions=5,
        )
        assert result.g1_better is False

    def test_efficiency_improvement(self):
        from metaengine.recursive_improvement import GenerationComparator
        comp = GenerationComparator()
        result = comp.compare(
            g0_experiments=20,
            g0_correct_predictions=10,
            g1_experiments=8,
            g1_correct_predictions=6,
        )
        # G1 uses fewer experiments AND has higher accuracy → efficiency improved
        assert result.efficiency_improved is True
        assert result.experiment_reduction > 0

    def test_result_hash(self):
        from metaengine.recursive_improvement import GenerationComparator
        comp = GenerationComparator()
        r1 = comp.compare(g0_experiments=10, g0_correct_predictions=5, g1_experiments=8, g1_correct_predictions=6)
        r2 = comp.compare(g0_experiments=10, g0_correct_predictions=5, g1_experiments=8, g1_correct_predictions=6)
        assert r1.result_hash == r2.result_hash

    def test_truth_effect_none(self):
        from metaengine.recursive_improvement import GenerationComparator
        comp = GenerationComparator()
        result = comp.compare(g0_experiments=10, g0_correct_predictions=5, g1_experiments=8, g1_correct_predictions=6)
        d = result.payload()
        assert d["truth_effect"] == "NONE"
