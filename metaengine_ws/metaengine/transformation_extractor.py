from __future__ import annotations

import hashlib
import re
from typing import Any

from .contracts import EvidenceRef, TypedTransformation


OPERATOR_PATTERNS = (
    ("SOURCE_READING", re.compile(r"\b(claim|assert|thesis|source|text|утверж|тезис|источник|текст)\w*", re.I)),
    ("HORIZON_DISCLOSURE", re.compile(r"\b(assum|premise|frame|horizon|предпосыл|горизонт|рамк)\w*", re.I)),
    ("RIVAL_FORK", re.compile(r"\b(rival|alternative|contradict|versus|альтернатив|сопер|противореч)\w*", re.I)),
    ("SEMANTIC_COUNTERFACTUAL", re.compile(r"\b(counterfactual|negat|scope|modality|контрфакт|отриц|модаль|област)\w*", re.I)),
    ("GENEALOGICAL_RETURN", re.compile(r"\b(history|historical|genealog|memory|истори|генеалог|памят)\w*", re.I)),
    ("EVIDENCE_DISCRIMINATOR", re.compile(r"\b(evidence|verify|citation|source ref|доказ|провер|ссылк)\w*", re.I)),
    ("DOUBLE_HERMENEUTIC", re.compile(r"\b(interpret|hermeneut|reader|интерпрет|герменевт|читател)\w*", re.I)),
    ("SUBLATION_WITH_RESIDUE", re.compile(r"\b(synthesis|residu|unresolved|tension|синтез|остат|неразреш|напряж)\w*", re.I)),
    ("OPERATOR_MUTATION", re.compile(r"\b(operator|method|reframe|mutation|оператор|метод|переформ|мутац)\w*", re.I)),
    ("SOURCE_RETURN", re.compile(r"\b(reground|return to source|source-bound|вернут.*источник|свер.*источник)\w*", re.I)),
)


def _candidate_strings(value: Any, path: str = "root"):
    if isinstance(value, str):
        cleaned = value.strip()
        if len(cleaned) >= 12:
            yield path, cleaned
    elif isinstance(value, dict):
        for key in sorted(value):
            yield from _candidate_strings(value[key], f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _candidate_strings(item, f"{path}[{index}]")


def _source_span(text: str, source_text: str, input_hash: str) -> tuple[EvidenceRef, ...]:
    start = source_text.find(text)
    if start < 0:
        return ()
    end = start + len(text)
    return (EvidenceRef(input_hash, start, end, hashlib.sha256(text.encode()).hexdigest()),)


def extract_transformations(canonical: dict[str, Any], native: dict[str, Any], source_text: str, input_hash: str, limit: int = 24) -> list[dict[str, Any]]:
    """Extract only transformations evidenced by actual adapter output.

    Empty or purely administrative output yields no transformations. There is deliberately no
    engine-id/type lookup: architecture labels cannot manufacture cognitive work.
    """

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path, text in _candidate_strings({"canonical": canonical, "native": native}):
        for transformation_type, pattern in OPERATOR_PATTERNS:
            if not pattern.search(text):
                continue
            key = (transformation_type, text[:240])
            if key in seen:
                continue
            seen.add(key)
            spans = _source_span(text, source_text, input_hash)
            transformation = TypedTransformation(
                transformation_type=transformation_type,
                proposition=text[:500],
                source_spans=spans,
                assumptions=() if spans else ("DERIVED_OUTPUT_REQUIRES_SOURCE_RETURN",),
                falsifier="Independent evidence or a stronger rival reading overturns this transformation",
                residual_tensions=() if spans else ("SOURCE_ALIGNMENT_UNVERIFIED",),
                provenance="ACTUAL_EXECUTOR_OUTPUT",
                metadata={"output_path": path, "source_reground_required": not bool(spans)},
            ).as_dict()
            transformation["peer_sources"] = []
            rows.append(transformation)
            if len(rows) >= limit:
                return rows
    return rows

