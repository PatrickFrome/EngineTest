"""METAENGINE Phase 18 — Sealed Benchmark Suite.

Generates benchmark tasks that are UNKNOWN to the engine's candidate
generator, policy evolution, and development workers. This ensures
capability gains are real, not benchmark overfitting.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .util import canonical_hash


SEALED_VERSION = "METAENGINE-SEALED-BENCHMARK-1"


class SealedDimension(str, Enum):
    REASONING_DEPTH = "reasoning_depth"
    LONG_HORIZON_COHERENCE = "long_horizon_coherence"
    PLANNING = "planning"
    ERROR_RECOVERY = "error_recovery"
    UNCERTAINTY_CALIBRATION = "uncertainty_calibration"
    NOVEL_PROBLEM_SOLVING = "novel_problem_solving"
    ROBUSTNESS_TO_MISLEADING_CONTEXT = "robustness_to_misleading_context"
    CONTEXT_COMPRESSION = "context_compression"


@dataclass(frozen=True)
class SealedTask:
    """A benchmark task unknown to the engine."""
    task_id: str
    sealed: bool
    source_text: str
    expected_outcome: dict[str, Any]
    capability_dimensions: tuple[str, ...]
    task_hash: str
    truth_effect: str

    def payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "sealed": self.sealed,
            "source_text": self.source_text,
            "expected_outcome": self.expected_outcome,
            "capability_dimensions": list(self.capability_dimensions),
            "task_hash": self.task_hash,
            "truth_effect": self.truth_effect,
            "claim_ceiling": "SEALED_TASK_IS_EVALUATIVE_NOT_TRUTH",
        }


_SEALED_TEMPLATES = [
    ("Analyze whether the argument in this text commits the fallacy of affirming the consequent. {context}", [SealedDimension.REASONING_DEPTH, SealedDimension.ERROR_RECOVERY]),
    ("Design a plan to resolve the contradiction described, using minimal steps. {context}", [SealedDimension.PLANNING, SealedDimension.LONG_HORIZON_COHERENCE]),
    ("Identify where the text's reasoning is most vulnerable to a counterexample, and construct one. {context}", [SealedDimension.REASONING_DEPTH, SealedDimension.NOVEL_PROBLEM_SOLVING]),
    ("The following text contains a subtle error. Find it and explain why it matters. {context}", [SealedDimension.ERROR_RECOVERY, SealedDimension.UNCERTAINTY_CALIBRATION]),
    ("Compress the essential argument of this text into 50 words without losing the key claim. {context}", [SealedDimension.CONTEXT_COMPRESSION, SealedDimension.LONG_HORIZON_COHERENCE]),
    ("This text is designed to mislead. Identify the misleading element and explain why it could cause an error. {context}", [SealedDimension.ROBUSTNESS_TO_MISLEADING_CONTEXT, SealedDimension.ERROR_RECOVERY]),
    ("Propose a novel solution to the problem described that does not appear in the text. {context}", [SealedDimension.NOVEL_PROBLEM_SOLVING, SealedDimension.PLANNING]),
    ("Evaluate your own confidence in the analysis of this text. Where are you most uncertain? {context}", [SealedDimension.UNCERTAINTY_CALIBRATION, SealedDimension.REASONING_DEPTH]),
]

_CONTEXTS = [
    "A study claims that correlation implies causation when the sample size exceeds 1000.",
    "The text argues that consciousness can be reduced to information processing without remainder.",
    "An experiment shows that removing component X degrades performance by 40%, but only in high-uncertainty tasks.",
    "A philosophical argument uses modal logic to prove that necessity is equivalent to universality across all possible worlds.",
    "The system claims to have learned to route tasks optimally, but the benchmark was not sealed from the routing mechanism.",
    "An analysis of distributed intelligence shows that federation outperforms single-model approaches, but only when resource budgets are equal.",
]


class SealedBenchmarkSuite:
    """Generates sealed benchmark tasks unknown to the engine."""

    def __init__(self, *, seed: int = 42):
        self._rng = random.Random(seed)
        self._seed = seed

    def generate_sealed_tasks(self, count: int = 5) -> tuple[SealedTask, ...]:
        tasks: list[SealedTask] = []
        for i in range(count):
            template, dims = self._rng.choice(_SEALED_TEMPLATES)
            context = self._rng.choice(_CONTEXTS)
            source_text = template.format(context=context)

            expected = {
                "must_identify": source_text[:50],
                "quality_threshold": 0.7,
                "dimension_scores": {d.value: 0.5 for d in dims},
            }

            task = SealedTask(
                task_id=f"sealed-{i:03d}",
                sealed=True,
                source_text=source_text,
                expected_outcome=expected,
                capability_dimensions=tuple(d.value for d in dims),
                task_hash="",
                truth_effect="NONE",
            )
            h = canonical_hash(task.payload())
            task = SealedTask(
                task_id=task.task_id, sealed=True,
                source_text=task.source_text, expected_outcome=task.expected_outcome,
                capability_dimensions=task.capability_dimensions,
                task_hash=h, truth_effect="NONE",
            )
            tasks.append(task)
        return tuple(tasks)

    def suite_hash(self) -> str:
        return canonical_hash({
            "sealed_version": SEALED_VERSION,
            "seed": self._seed,
            "task_count": len(self.generate_sealed_tasks()),
        })
