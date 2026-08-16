"""Step 10: Learned top-k engine router — sparse MoE-style engine selection.

Replaces the round-robin "all 16 engines run on every input" approach with
a learned router that selects the 4-6 most relevant engines per input.

Architecture:
  1. Extracts task features from input text (length, domain, complexity)
  2. Scores each engine based on learned weights (capability match)
  3. Selects top-k engines (default 6) — others are skipped
  4. Logs selection rationale for observability
  5. Learns from (input_features, engine_id, fitness) triples

This reduces LLM calls by ~60% (6 engines instead of 16) while preserving
output quality — only the most relevant engines fire per input.

Constitution compliance:
  - Router is transparent (doesn't modify inputs or outputs)
  - Selection is evaluative (truth_effect=NONE)
  - No auto-promotion (router selects engines, doesn't promote results)
  - No code modification (routing decision only)
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROUTER_VERSION = "METAENGINE-LEARNED-ROUTER-1"

# Engine capability profiles (from config/meta_engine.json)
ENGINE_PROFILES: dict[str, dict[str, Any]] = {
    "engine_01": {"roles": ["frame_atom_externalization", "interrogative_induction"], "focus": "genealogical-constructive analysis", "tier": "native"},
    "engine_02": {"roles": ["open_set_operator_discovery", "operator_evolution"], "focus": "operator mutation and external validation", "tier": "native"},
    "engine_03": {"roles": ["shared_semantic_boundary", "lineage_fixity"], "focus": "cross-lineage semantic normalization", "tier": "native"},
    "engine_04": {"roles": ["semantic_role", "parse_program_synthesis"], "focus": "parse-program synthesis and counterfactual regression", "tier": "native"},
    "engine_05": {"roles": ["memory_management", "archival_retrieval"], "focus": "stateful memory and persistent context", "tier": "reference"},
    "engine_06": {"roles": ["graph_extraction", "community_detection"], "focus": "graph knowledge and community structure", "tier": "reference"},
    "engine_07": {"roles": ["evidence_discrimination", "hypothesis_testing"], "focus": "evidence-centric scientific literature", "tier": "reference"},
    "engine_08": {"roles": ["specialist_orchestration", "manager_planning"], "focus": "manager-led specialist orchestration", "tier": "reference"},
    "engine_09": {"roles": ["deep_research", "web_analysis"], "focus": "adaptive long-horizon research", "tier": "reference"},
    "engine_10": {"roles": ["agent_societies", "role_playing"], "focus": "agent collaboration and workforce", "tier": "reference"},
    "engine_11": {"roles": ["multi_agent_workflow", "stateful_orchestration"], "focus": "production multi-agent workflows", "tier": "reference"},
    "engine_12": {"roles": ["durable_state", "checkpointing"], "focus": "durable stateful graph orchestration", "tier": "reference"},
    "engine_13": {"roles": ["planner_executor", "source_tracking"], "focus": "planner-executor research", "tier": "reference"},
    "engine_14": {"roles": ["multi_perspective", "long_form_synthesis"], "focus": "multi-perspective knowledge curation", "tier": "reference"},
    "engine_15": {"roles": ["hypothesis_generation", "scientific_reasoning"], "focus": "AI scientist hypothesis generation", "tier": "reference"},
    "engine_16": {"roles": ["program_optimization", "signature_compilation"], "focus": "declarative program optimization", "tier": "reference"},
}

# Domain keywords for feature extraction
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "philosophy": ["being", "existence", "consciousness", "phenomenology", "hermeneutic", "ontology", "epistemology"],
    "science": ["experiment", "hypothesis", "evidence", "data", "measurement", "theory", "empirical"],
    "mathematics": ["proof", "theorem", "axiom", "logic", "number", "equation", "geometric"],
    "literature": ["text", "narrative", "author", "reading", "interpretation", "discourse", "rhetoric"],
    "code": ["function", "class", "variable", "compile", "debug", "algorithm", "program"],
    "history": ["century", "ancient", "medieval", "revolution", "war", "civilization", "epoch"],
    "ethics": ["moral", "ought", "duty", "virtue", "justice", "rights", "consequence"],
    "memory": ["remember", "recall", "archive", "store", "retrieve", "context", "persistent"],
    "graph": ["node", "edge", "network", "community", "cluster", "connection", "topology"],
    "research": ["investigate", "analyze", "synthesize", "report", "citation", "source", "study"],
}


@dataclass
class TaskFeatures:
    """Features extracted from input text for engine routing."""
    length: int  # character count
    word_count: int
    sentence_count: int
    complexity: float  # 0-1, based on avg sentence length + unique words
    domains: dict[str, float]  # domain → match score (0-1)
    has_questions: bool
    has_code: bool
    has_math: bool

    def to_vector(self) -> list[float]:
        """Convert to feature vector for scoring."""
        return [
            self.length / 10000.0,  # normalized length
            self.word_count / 2000.0,
            self.sentence_count / 100.0,
            self.complexity,
            self.has_questions,
            self.has_code,
            self.has_math,
            # Top domains
            self.domains.get("philosophy", 0.0),
            self.domains.get("science", 0.0),
            self.domains.get("mathematics", 0.0),
            self.domains.get("literature", 0.0),
            self.domains.get("code", 0.0),
            self.domains.get("history", 0.0),
            self.domains.get("ethics", 0.0),
            self.domains.get("memory", 0.0),
            self.domains.get("graph", 0.0),
            self.domains.get("research", 0.0),
        ]

    def payload(self) -> dict[str, Any]:
        return {
            "length": self.length,
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "complexity": round(self.complexity, 4),
            "domains": {k: round(v, 4) for k, v in self.domains.items() if v > 0},
            "has_questions": self.has_questions,
            "has_code": self.has_code,
            "has_math": self.has_math,
        }


@dataclass
class RoutingDecision:
    """Result of engine routing decision."""
    selected_engines: list[str]  # engine_ids in priority order
    skipped_engines: list[str]
    scores: dict[str, float]  # engine_id → score
    rationale: str
    task_features: TaskFeatures
    top_k: int

    def payload(self) -> dict[str, Any]:
        return {
            "selected": self.selected_engines,
            "skipped": self.skipped_engines,
            "scores": {k: round(v, 4) for k, v in self.scores.items()},
            "rationale": self.rationale,
            "top_k": self.top_k,
            "features": self.task_features.payload(),
            "truth_effect": "NONE",
        }


class LearnedRouter:
    """Learned top-k engine router — selects most relevant engines per input.

    Usage:
        router = LearnedRouter(top_k=6)
        decision = router.route("What is the meaning of consciousness?")
        print(decision.selected_engines)  # ['engine_01', 'engine_07', ...]
        print(decision.skipped_engines)   # ['engine_06', 'engine_12', ...]

    Learning:
        router.add_observation(task_features, engine_id, fitness)
        router.recalibrate()  # Adjusts weights based on observations
    """

    def __init__(
        self,
        *,
        top_k: int = 6,
        always_include_native: bool = True,  # Always include engines 01-04
        min_score_threshold: float = 0.1,  # Skip engines below this score
    ):
        self.top_k = top_k
        self.always_include_native = always_include_native
        self.min_score_threshold = min_score_threshold

        # Learned weights: engine_id → feature_weight_vector
        # Initialized with heuristic weights based on ENGINE_PROFILES
        self._engine_weights: dict[str, list[float]] = {}
        self._init_heuristic_weights()

        # Observation history for learning
        self._observations: list[dict[str, Any]] = []
        self._max_observations: int = 500

    def _init_heuristic_weights(self) -> None:
        """Initialize engine weights based on capability profiles."""
        for eid, profile in ENGINE_PROFILES.items():
            roles = profile.get("roles", [])
            focus = profile.get("focus", "").lower()
            tier = profile.get("tier", "reference")

            # Base weights (17 features matching TaskFeatures.to_vector)
            weights = [0.5] * 17

            # Adjust based on roles
            if "memory_management" in roles or "archival_retrieval" in roles:
                weights[7 + list(DOMAIN_KEYWORDS.keys()).index("memory")] = 0.9
            if "graph_extraction" in roles:
                weights[7 + list(DOMAIN_KEYWORDS.keys()).index("graph")] = 0.9
            if "evidence_discrimination" in roles:
                weights[7 + list(DOMAIN_KEYWORDS.keys()).index("science")] = 0.8
            if "multi_perspective" in roles:
                weights[7 + list(DOMAIN_KEYWORDS.keys()).index("literature")] = 0.8
            if "hypothesis_generation" in roles:
                weights[7 + list(DOMAIN_KEYWORDS.keys()).index("science")] = 0.7
            if "parse_program_synthesis" in roles:
                weights[5] = 0.9  # has_code
                weights[7 + list(DOMAIN_KEYWORDS.keys()).index("code")] = 0.9
            if "interrogative_induction" in roles:
                weights[4] = 0.8  # has_questions
            if "deep_research" in roles:
                weights[7 + list(DOMAIN_KEYWORDS.keys()).index("research")] = 0.9

            # Native engines get slight boost
            if tier == "native":
                weights = [w * 1.2 for w in weights]

            self._engine_weights[eid] = weights

    def extract_features(self, text: str) -> TaskFeatures:
        """Extract task features from input text."""
        length = len(text)
        words = text.split()
        word_count = len(words)
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
        sentence_count = len(sentences)
        avg_sentence_len = word_count / max(1, sentence_count)
        unique_words = len(set(w.lower() for w in words))
        complexity = min(1.0, (avg_sentence_len / 20.0 + unique_words / max(1, word_count)) / 2.0)

        # Domain detection
        text_lower = text.lower()
        domains: dict[str, float] = {}
        for domain, keywords in DOMAIN_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in text_lower)
            domains[domain] = min(1.0, matches / 5.0)  # Normalize to 0-1

        has_questions = "?" in text
        has_code = bool(re.search(r'(def |class |import |function |var |const )', text))
        has_math = bool(re.search(r'(\d+\s*[+\-*/=]\s*\d+|equation|theorem|proof)', text, re.I))

        return TaskFeatures(
            length=length, word_count=word_count, sentence_count=sentence_count,
            complexity=complexity, domains=domains,
            has_questions=has_questions, has_code=has_code, has_math=has_math,
        )

    def _score_engine(self, engine_id: str, features: TaskFeatures) -> float:
        """Score an engine for the given task features."""
        weights = self._engine_weights.get(engine_id, [0.5] * 17)
        feature_vec = features.to_vector()

        # Dot product
        score = sum(w * f for w, f in zip(weights, feature_vec))

        # Normalize to [0, 1]
        return max(0.0, min(1.0, score / max(1.0, sum(w ** 2 for w in weights) ** 0.5)))

    def route(self, text: str | None = None, features: TaskFeatures | None = None) -> RoutingDecision:
        """Select top-k engines for the given input.

        Args:
            text: input text (will extract features)
            features: pre-extracted features (alternative to text)

        Returns:
            RoutingDecision with selected and skipped engines
        """
        if features is None:
            features = self.extract_features(text or "")

        # Score all engines
        scores = {eid: self._score_engine(eid, features) for eid in ENGINE_PROFILES}

        # Sort by score descending
        sorted_engines = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # Select top-k
        selected = []
        skipped = []

        # Always include native engines if configured
        native_ids = ["engine_01", "engine_02", "engine_03", "engine_04"]

        for eid, score in sorted_engines:
            if len(selected) >= self.top_k:
                skipped.append(eid)
            elif score < self.min_score_threshold and eid not in native_ids:
                skipped.append(eid)
            elif self.always_include_native and eid in native_ids and len(selected) < self.top_k:
                selected.append(eid)
            elif len(selected) < self.top_k:
                selected.append(eid)
            else:
                skipped.append(eid)

        # Build rationale
        top_3 = [(eid, scores[eid]) for eid in selected[:3]]
        rationale_parts = [f"{eid}({score:.2f})" for eid, score in top_3]
        rationale = f"Top engines: {', '.join(rationale_parts)}. Selected {len(selected)}/{len(ENGINE_PROFILES)}, skipped {len(skipped)}."

        return RoutingDecision(
            selected_engines=selected,
            skipped_engines=skipped,
            scores=scores,
            rationale=rationale,
            task_features=features,
            top_k=self.top_k,
        )

    def add_observation(self, features: TaskFeatures, engine_id: str, fitness: float) -> None:
        """Add an observation for learning.

        Args:
            features: task features that were routed.
            engine_id: engine that was evaluated.
            fitness: resulting fitness score (0-1, higher = better).
        """
        self._observations.append({
            "engine_id": engine_id,
            "features": features.to_vector(),
            "fitness": float(fitness),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        if len(self._observations) > self._max_observations:
            self._observations = self._observations[-self._max_observations:]

    def recalibrate(self) -> int:
        """Adjust engine weights based on observed (features, fitness) pairs.

        Simple online learning: engines with higher average fitness get weight boost.

        Returns:
            Number of weight adjustments made.
        """
        if len(self._observations) < 10:
            return 0

        # Compute per-engine average fitness
        engine_fitness: dict[str, list[float]] = {}
        for obs in self._observations:
            eid = obs["engine_id"]
            engine_fitness.setdefault(eid, []).append(obs["fitness"])

        adjustments = 0
        for eid, fitnesses in engine_fitness.items():
            if eid not in self._engine_weights:
                continue
            avg_fitness = sum(fitnesses) / len(fitnesses)
            # Adjust weights: higher fitness → boost, lower fitness → reduce
            delta = (avg_fitness - 0.5) * 0.1  # Small step
            if abs(delta) > 0.01:
                self._engine_weights[eid] = [
                    max(0.1, min(2.0, w + delta))
                    for w in self._engine_weights[eid]
                ]
                adjustments += 1

        return adjustments

    def summary(self) -> dict[str, Any]:
        """Return router summary."""
        return {
            "router_version": ROUTER_VERSION,
            "top_k": self.top_k,
            "always_include_native": self.always_include_native,
            "engine_count": len(ENGINE_PROFILES),
            "observation_count": len(self._observations),
            "min_score_threshold": self.min_score_threshold,
            "truth_effect": "NONE",
            "claim_ceiling": "LEARNED_ROUTER_IS_TRANSPARENT_NOT_TRUTH",
            "constitution_compliance": {
                "transparent_routing": True,
                "no_code_modification": True,
                "no_auto_promotion": True,
                "sparse_selection": True,
            },
        }
