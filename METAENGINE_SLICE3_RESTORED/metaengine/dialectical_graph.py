from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .architecture_policy import ArchitecturePolicy
from .util import canonical_hash


def _sentences(text: str) -> list[tuple[int, int, str]]:
    rows = []
    for match in re.finditer(r"[^.!?\n]+(?:[.!?]|$)", text):
        value = match.group(0).strip()
        if value:
            start = text.find(value, match.start(), match.end())
            rows.append((start, start + len(value), value))
    return rows or [(0, len(text), text)]


def _span(source_id: str, start: int, end: int, text: str) -> dict[str, Any]:
    return {"source_id": source_id, "start": start, "end": end, "text_hash": hashlib.sha256(text.encode()).hexdigest(), "kind": "ORIGINAL_SOURCE_SPAN"}


class DialecticalGraphBuilder:
    """Builds a typed hermeneutic graph without granting derived nodes truth authority."""

    def build(self, source_text: str, source_id: str, policy: ArchitecturePolicy,
              engine_contributions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        policy.validate()
        sentences = _sentences(source_text)[:8]
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        by_operator: dict[str, list[str]] = {}
        engine_nodes: dict[str, str] = {}  # R5: engine_id → node_id

        def add(operator: str, proposition: str, spans=(), **extra):
            node = {
                "operator": operator,
                "proposition": proposition[:700],
                "source_spans": list(spans),
                "assumptions": list(extra.pop("assumptions", ())),
                "rival_id": extra.pop("rival_id", None),
                "falsifier": extra.pop("falsifier", None),
                "residual_tensions": list(extra.pop("residual_tensions", ())),
                "confidence": float(extra.pop("confidence", 0.0)),
                "abstention_reason": extra.pop("abstention_reason", None),
                "truth_status": "GENERATIVE_ONLY" if operator != "SOURCE_READING" else "SOURCE_BOUNDED_READING_NOT_VERIFIED_FACT",
                "truth_effect": "NONE",
                **extra,
            }
            node["node_id"] = "dial-" + canonical_hash(node)[:20]
            nodes.append(node)
            by_operator.setdefault(operator, []).append(node["node_id"])
            return node

        active = set(policy.dialectic_operators)
        readings = []
        if "SOURCE_READING" in active:
            for start, end, sentence in sentences[:4]:
                readings.append(add("SOURCE_READING", sentence, (_span(source_id, start, end, sentence),), confidence=0.55, falsifier="A source-context or attribution check changes the reading"))

        if "HORIZON_DISCLOSURE" in active:
            markers = sorted(set(re.findall(r"\b(?:must|may|should|only|never|always|может|должен|только|никогда|всегда)\b", source_text, re.I)))
            add("HORIZON_DISCLOSURE", "Interpretive horizon exposes modality and framing assumptions: " + (", ".join(markers) or "no explicit modal marker"), assumptions=("LEXICAL_MARKERS_DO_NOT_EXHAUST_INTERPRETIVE_HORIZON",), residual_tensions=("READER_POSITION_REMAINS_PARTIALLY_TACIT",))

        rivals = []
        if "RIVAL_FORK" in active:
            bases = readings[:2] or [add("SOURCE_READING", sentence, (_span(source_id, start, end, sentence),), confidence=0.4) for start, end, sentence in sentences[:2]]
            for index, base in enumerate(bases, 1):
                pair = f"rival-{index:02d}"
                literal = add("RIVAL_FORK", "Literal/charitable reading: " + base["proposition"], base["source_spans"], rival_id=pair, assumptions=("MAXIMIZE_LOCAL_COHERENCE",), falsifier="Broader context defeats the literal reading", residual_tensions=("ATTRIBUTION_OR_SCOPE_MAY_SHIFT",))
                resistant = add("RIVAL_FORK", "Resistant reading: the same wording may expose a limit, presupposition, or inversion rather than endorsement", base["source_spans"], rival_id=pair, assumptions=("TEST_NON_ENDORSEMENT_AND_SCOPE",), falsifier="Context explicitly fixes endorsement and scope", residual_tensions=("RIVALS_REMAIN_UNRESOLVED",))
                rivals.extend((literal, resistant)); edges.append({"from": literal["node_id"], "to": resistant["node_id"], "type": "MATERIAL_RIVAL", "truth_effect": "NONE"})

        if "SEMANTIC_COUNTERFACTUAL" in active:
            base = readings[0] if readings else None
            spans = base["source_spans"] if base else ()
            node = add("SEMANTIC_COUNTERFACTUAL", "Counterfactual probe: alter negation, modality, attribution, or scope and test which dependencies change", spans, assumptions=("COUNTERFACTUAL_IS_A_PROBE_NOT_A_SOURCE_CLAIM",), falsifier="The transformation leaves all downstream interpretations invariant", residual_tensions=("ORIGINAL_AND_COUNTERFACTUAL_MUST_NOT_BE_CONFLATED",))
            if base: edges.append({"from": base["node_id"], "to": node["node_id"], "type": "COUNTERFACTUAL_OF", "truth_effect": "NONE"})

        if "GENEALOGICAL_RETURN" in active:
            add("GENEALOGICAL_RETURN", "Genealogical return: ask which historical transformation made the current vocabulary and exclusions possible", assumptions=("HISTORICAL_EVIDENCE_NOT_PRESENT_UNLESS_CITED",), falsifier="Independent history shows continuity without the proposed transformation", residual_tensions=("GENEALOGY_REQUIRES_EXTERNAL_EVIDENCE",), abstention_reason="No external historical corpus is available in this run")

        if "EVIDENCE_DISCRIMINATOR" in active:
            spans = tuple(span for row in readings for span in row["source_spans"][:1])
            add("EVIDENCE_DISCRIMINATOR", "Discriminating evidence must decide among rival attribution, scope, and causal readings without relying on vote count", spans, assumptions=("EXACT_SPANS_ARE_NECESSARY_BUT_NOT_SUFFICIENT_FOR_ENTAILMENT",), falsifier="The proposed evidence is equally compatible with all rivals", residual_tensions=("ENTAILMENT_REQUIRES_INDEPENDENT_VERIFICATION",))

        if "DOUBLE_HERMENEUTIC" in active:
            add("DOUBLE_HERMENEUTIC", "Interpret both the source and the analytic operators through which the source becomes legible; expose how the observer changes the question", assumptions=("THE_ANALYTIC_OPERATOR_IS_HISTORICALLY_SITUATED",), falsifier="Alternative operators yield no material change", residual_tensions=("SELF_DESCRIPTION_CANNOT_FULLY_ESCAPE_ITS_OWN_HORIZON",))

        if "SUBLATION_WITH_RESIDUE" in active:
            add("SUBLATION_WITH_RESIDUE", "Conditional synthesis preserves the strongest shared dependency while retaining irreducible rival residues", assumptions=("SYNTHESIS_HAS_NO_TRUTH_AUTHORITY",), falsifier="The shared dependency disappears under source return", residual_tensions=tuple(sorted({t for rival in rivals for t in rival["residual_tensions"]}) or {"NO_VALIDATED_RIVAL_PAIR"}), abstention_reason=None if rivals else "No rival pair was constructed")

        if "OPERATOR_MUTATION" in active:
            add("OPERATOR_MUTATION", "If recursive return creates only echoes, replace the analytic operator rather than multiplying equivalent branches", assumptions=("OPERATOR_CHANGE_REQUIRES_OUTCOME_VALIDATION",), falsifier="The new operator does not improve an external outcome", residual_tensions=("MUTATION_REMAINS_SHADOW_UNTIL_PROMOTED",))

        if "SOURCE_RETURN" in active:
            for reading in readings[:3]:
                node = add("SOURCE_RETURN", "Return to exact source span before any promotion: " + reading["proposition"], reading["source_spans"], falsifier="Span hash or boundaries fail validation", confidence=0.7)
                edges.append({"from": reading["node_id"], "to": node["node_id"], "type": "REGROUNDS", "truth_effect": "NONE"})

        # R5: TRUE multi-engine discourse — add engine contribution nodes
        if engine_contributions:
            for contrib in engine_contributions[:8]:
                eid = contrib.get('engine_id', 'unknown')
                canonical = contrib.get('canonical', '')
                status = contrib.get('status', 'COMPLETED')
                if isinstance(canonical, dict):
                    canonical_str = json.dumps(canonical, ensure_ascii=False, default=str)[:300]
                else:
                    canonical_str = str(canonical)[:300]
                if not canonical_str or status == 'FAILED':
                    continue
                engine_node = add("SOURCE_READING", f"[{eid}] {canonical_str}", (), confidence=0.6, falsifier="Engine output conflicts with source evidence", **{"engine_id": eid, "engine_status": status})
                engine_nodes[eid] = engine_node["node_id"]

            engine_ids_list = list(engine_nodes.keys())
            for i, eid1 in enumerate(engine_ids_list):
                for eid2 in engine_ids_list[i+1:]:
                    node1 = next(n for n in nodes if n["node_id"] == engine_nodes[eid1])
                    node2 = next(n for n in nodes if n["node_id"] == engine_nodes[eid2])
                    if node1["proposition"][:100] != node2["proposition"][:100]:
                        fork_node = add("RIVAL_FORK", f"[{eid1} vs {eid2}] Disagreement: {eid1} reads the source as '{node1['proposition'][:60]}...' while {eid2} reads it as '{node2['proposition'][:60]}...' — divergent interpretations", (), assumptions=("ENGINE_DISAGREEMENT_IS_PRODUCTIVE_NOT_DESTRUCTIVE",), falsifier="Engines converge on identical reading under different conditions", residual_tensions=("RESIDUAL_DIFFERENCE_MAY_INDICATE_COMPLEMENTARY_PERSPECTIVES",), rival_id=f"{eid1}__{eid2}", confidence=0.5, **{"engine_pair": f"{eid1},{eid2}"})
                        edges.append({"from": engine_nodes[eid1], "to": fork_node["node_id"], "type": "RIVAL_FORK_FROM", "truth_effect": "NONE"})
                        edges.append({"from": engine_nodes[eid2], "to": fork_node["node_id"], "type": "RIVAL_FORK_FROM", "truth_effect": "NONE"})

            if len(engine_nodes) >= 2:
                add("EVIDENCE_DISCRIMINATOR", f"Cross-engine evidence discrimination: {len(engine_nodes)} engines produced outputs; determine which readings are best supported by source evidence", (), assumptions=("ENGINE_OUTPUTS_ARE_GENERATIVE_NOT_AUTHORITATIVE",), falsifier="All engines produce identical readings (no discrimination possible)", residual_tensions=("DISCRIMINATION_REQUIRES_EXTERNAL_VERIFICATION",), confidence=0.4, **{"engine_count": len(engine_nodes), "engines_compared": list(engine_nodes.keys())})
                add("SUBLATION_WITH_RESIDUE", f"Conditional synthesis across {len(engine_nodes)} engine readings: preserve the strongest shared insight while retaining irreducible inter-engine differences", (), assumptions=("SYNTHESIS_HAS_NO_TRUTH_AUTHORITY",), falsifier="The shared dependency disappears under source return", residual_tensions=("INTER_ENGINE_DIFFERENCES_MAY_BE_IRREDUCIBLE",), confidence=0.45, **{"engines_synthesized": list(engine_nodes.keys())})

        for operator, ids in by_operator.items():
            for left, right in zip(ids, ids[1:]):
                edges.append({"from": left, "to": right, "type": "OPERATOR_RECURRENCE", "truth_effect": "NONE"})
        graph = {
            "graph_version": "16X-TYPED-DIALECTICAL-GRAPH-2.3",
            "source_id": source_id,
            "policy_hash": policy.policy_hash,
            "operators_requested": list(policy.dialectic_operators),
            "operators_realized": sorted(by_operator),
            "nodes": nodes,
            "edges": edges,
            "metrics": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "operator_count": len(by_operator),
                "source_bound_nodes": sum(bool(node["source_spans"]) for node in nodes),
                "rival_pairs": len({node["rival_id"] for node in nodes if node.get("rival_id")}),
                "residual_tension_nodes": sum(bool(node["residual_tensions"]) for node in nodes),
            },
            "claim_ceiling": "DIALECTICAL_DEPTH_IS_GENERATIVE_UNTIL_EXTERNALLY_VERIFIED",
        }
        graph["graph_hash"] = canonical_hash({key: value for key, value in graph.items() if key != "graph_hash"})
        return graph

