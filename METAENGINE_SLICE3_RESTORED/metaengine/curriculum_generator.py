"""METAENGINE Phase 14 — Curriculum / Task Generator.

Automatically generates discriminative benchmark tasks that can distinguish
between architecture candidates. Tasks have progressive difficulty and
target specific capabilities.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from .util import canonical_hash


CURRICULUM_VERSION = "METAENGINE-CURRICULUM-GENERATOR-1"


class DifficultyLevel(str, Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    ADVERSARIAL = "ADVERSARIAL"


_CAPABILITY_DOMAINS = (
    "REASONING", "PLANNING", "EVIDENCE", "TOOL_USE", "MEMORY",
    "CREATIVITY", "ANALYSIS", "SYNTHESIS", "CRITIQUE", "RETRIEVAL",
)

_TASK_TEMPLATES = {
    DifficultyLevel.EASY: [
        "Analyze the following text and identify the main claim. {context}",
        "Summarize the key points in this passage. {context}",
        "What evidence supports the conclusion in this text? {context}",
    ],
    DifficultyLevel.MEDIUM: [
        "Compare two competing interpretations of this text and explain which is better supported. {context}",
        "Identify a hidden assumption in this argument and explain why it matters. {context}",
        "Generate a counterargument to the main claim in this text. {context}",
    ],
    DifficultyLevel.HARD: [
        "Synthesize a novel perspective that reconciles the tensions in this text without erasing any position. {context}",
        "Identify what additional evidence would be needed to resolve the central question, and explain why current evidence is insufficient. {context}",
        "Construct a falsifiable hypothesis about the causal mechanism behind the phenomenon described. {context}",
    ],
    DifficultyLevel.ADVERSARIAL: [
        "Find a case where the reasoning in this text would lead to a catastrophic failure, and explain why. {context}",
        "Argue that the approach in this text is fundamentally wrong, using only evidence from the text itself. {context}",
        "Design an experiment that could falsify the central claim, using minimal resources. {context}",
    ],
}

_CONTEXTS = [
    "The source describes a tension between evidence and generative reasoning in epistemic systems.",
    "A philosophical argument about necessity and contingency in modal logic is presented.",
    "The text examines how distributed intelligence systems can avoid self-confirmation bias.",
    "An analysis of counterfactual reasoning and its limitations in causal attribution.",
    "The passage discusses whether majority voting can ever establish scientific truth.",
    "A critical examination of how memory architecture affects long-horizon coherence.",
    "The source explores the relationship between architectural diversity and problem-solving quality.",
    "An investigation into whether sparse conditional routing improves quality under equal resource budgets.",
]


@dataclass(frozen=True)
class CurriculumTask:
    """A generated benchmark task for architecture evaluation."""
    task_id: str
    difficulty: DifficultyLevel
    source_text: str
    capability_targets: tuple[str, ...]
    task_hash: str

    def payload(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "difficulty": self.difficulty.value,
            "source_text": self.source_text,
            "capability_targets": list(self.capability_targets),
            "task_hash": self.task_hash,
            "truth_effect": "NONE",
            "claim_ceiling": "CURRICULUM_TASK_IS_EVALUATIVE_NOT_TRUTH",
        }


class CurriculumGenerator:
    """Generates discriminative benchmark tasks with progressive difficulty."""

    def __init__(self, *, seed: int = 42):
        self._rng = random.Random(seed)

    def generate(
        self,
        *,
        count: int = 5,
        progressive: bool = False,
    ) -> tuple[CurriculumTask, ...]:
        """Generate curriculum tasks.

        Args:
            count: Number of tasks to generate.
            progressive: If True, tasks are sorted by difficulty (EASY → ADVERSARIAL).
        """
        tasks: list[CurriculumTask] = []
        for i in range(count):
            if progressive:
                # Distribute across difficulty levels
                levels = list(DifficultyLevel)
                difficulty = levels[min(i * len(levels) // max(1, count), len(levels) - 1)]
            else:
                difficulty = self._rng.choice(list(DifficultyLevel))

            template = self._rng.choice(_TASK_TEMPLATES[difficulty])
            context = self._rng.choice(_CONTEXTS)
            source_text = template.format(context=context)

            # Target 1-3 capabilities
            k = self._rng.randint(1, 3)
            caps = tuple(sorted(self._rng.sample(_CAPABILITY_DOMAINS, k)))

            task = CurriculumTask(
                task_id=f"curriculum-{i:03d}-{difficulty.value.lower()}",
                difficulty=difficulty,
                source_text=source_text,
                capability_targets=caps,
                task_hash="",
            )
            h = canonical_hash(task.payload())
            task = CurriculumTask(
                task_id=task.task_id,
                difficulty=task.difficulty,
                source_text=task.source_text,
                capability_targets=task.capability_targets,
                task_hash=h,
            )
            tasks.append(task)

        if progressive:
            tasks.sort(key=lambda t: list(DifficultyLevel).index(t.difficulty))

        return tuple(tasks)
