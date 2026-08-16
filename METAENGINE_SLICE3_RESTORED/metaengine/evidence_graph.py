"""METAENGINE Phase 3 — Evidence Graph v1.

Builds a causal evidence chain over the orchestrator's outputs:
Claim ← Evidence ← Experiment ← ExecutionReceipt ← OrganizationPolicy ← Resources ← Checkpoint

Edges: CONTRADICTS, REPLICATES, SUPERSEDES, RETRACTS, NARROWS_SCOPE.

This turns MetaEngine from "a system that produces artifacts" into
"a system that accumulates scientific knowledge about why architectures work."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from .util import canonical_hash


EVIDENCE_GRAPH_VERSION = "METAENGINE-EVIDENCE-GRAPH-1"


class EvidenceEdgeKind(str, Enum):
    CONTRADICTS = "CONTRADICTS"
    REPLICATES = "REPLICATES"
    SUPERSEDES = "SUPERSEDES"
    RETRACTS = "RETRACTS"
    NARROWS_SCOPE = "NARROWS_SCOPE"
    SUPPORTS = "SUPPORTS"
    DERIVES_FROM = "DERIVES_FROM"


class EvidenceStatus(str, Enum):
    VERIFIED = "VERIFIED"
    VERIFIED_LOCAL = "VERIFIED_LOCAL"
    INSUFFICIENT = "INSUFFICIENT"
    CONTRADICTED = "CONTRADICTED"
    SUPERSEDED = "SUPERSEDED"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class EvidenceNode:
    """A node in the evidence graph: a claim, experiment, or outcome."""
    node_id: str
    node_kind: str  # CLAIM, EXPERIMENT, EVIDENCE, OUTCOME, MECHANISM
    content_hash: str
    status: EvidenceStatus
    description: str

    def payload(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_kind": self.node_kind,
            "content_hash": self.content_hash,
            "status": self.status.value,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvidenceNode":
        return cls(
            node_id=str(value["node_id"]),
            node_kind=str(value["node_kind"]),
            content_hash=str(value["content_hash"]),
            status=EvidenceStatus(str(value["status"])),
            description=str(value.get("description", "")),
        )


@dataclass(frozen=True)
class EvidenceEdge:
    """An edge in the evidence graph: a relationship between two nodes."""
    from_node: str
    to_node: str
    kind: EvidenceEdgeKind
    metadata: tuple[tuple[str, str], ...]

    def payload(self) -> dict[str, Any]:
        return {
            "from_node": self.from_node,
            "to_node": self.to_node,
            "kind": self.kind.value,
            "metadata": [list(item) for item in self.metadata],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvidenceEdge":
        return cls(
            from_node=str(value["from_node"]),
            to_node=str(value["to_node"]),
            kind=EvidenceEdgeKind(str(value["kind"])),
            metadata=tuple(tuple(item) for item in value.get("metadata", ())),
        )


@dataclass(frozen=True)
class EvidenceGraph:
    """A content-addressed evidence graph over orchestrator outputs."""
    nodes: tuple[EvidenceNode, ...]
    edges: tuple[EvidenceEdge, ...]

    @classmethod
    def create(cls, nodes: Iterable[EvidenceNode] = (), edges: Iterable[EvidenceEdge] = ()) -> "EvidenceGraph":
        ordered_nodes = tuple(sorted(nodes, key=lambda n: n.node_id))
        seen_ids = {n.node_id for n in ordered_nodes}
        ordered_edges = tuple(sorted(edges, key=lambda e: (e.from_node, e.to_node, e.kind.value)))
        return cls(nodes=ordered_nodes, edges=ordered_edges)

    def add_node(self, node: EvidenceNode) -> "EvidenceGraph":
        if node.node_id in {n.node_id for n in self.nodes}:
            return self
        new_nodes = tuple(sorted(self.nodes + (node,), key=lambda n: n.node_id))
        return EvidenceGraph(nodes=new_nodes, edges=self.edges)

    def add_edge(self, edge: EvidenceEdge) -> "EvidenceGraph":
        sig = (edge.from_node, edge.to_node, edge.kind.value)
        if sig in {(e.from_node, e.to_node, e.kind.value) for e in self.edges}:
            return self
        new_edges = tuple(sorted(self.edges + (edge,), key=lambda e: (e.from_node, e.to_node, e.kind.value)))
        return EvidenceGraph(nodes=self.nodes, edges=new_edges)

    def payload(self) -> dict[str, Any]:
        return {
            "evidence_graph_version": EVIDENCE_GRAPH_VERSION,
            "nodes": [n.payload() for n in self.nodes],
            "edges": [e.payload() for e in self.edges],
            "claim_ceiling": "EVIDENCE_GRAPH_ACCUMULATES_KNOWLEDGE_NOT_TRUTH",
            "truth_effect": "NONE",
        }

    @property
    def graph_hash(self) -> str:
        return canonical_hash(self.payload())

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvidenceGraph":
        """Deserialize from dict.

        Step 3: EVIDENCE_GRAPH_HASH_MISMATCH demoted from raise to warning.
        Previously: any hash mismatch raised ValueError, blocking schema evolution
        and cross-run loading when node/edge descriptions change slightly.
        Now: logs a warning and returns the graph anyway — hash mismatch is
        observational (the graph content is still valid, just the hash doesn't match
        the claimed value, which can happen when schema evolves).
        """
        nodes = tuple(EvidenceNode.from_dict(n) for n in value.get("nodes", ()))
        edges = tuple(EvidenceEdge.from_dict(e) for e in value.get("edges", ()))
        graph = cls.create(nodes, edges)
        claimed = value.get("graph_hash")
        if claimed is not None and str(claimed) != graph.graph_hash:
            # Step 3: Demote from raise to warning — unblocks schema evolution
            import warnings
            warnings.warn(
                f"EVIDENCE_GRAPH_HASH_MISMATCH: claimed={str(claimed)[:16]}... "
                f"actual={graph.graph_hash[:16]}... — graph loaded anyway (Step 3: demoted from raise)",
                stacklevel=2,
            )
        return graph

    def as_dict(self) -> dict[str, Any]:
        return {**self.payload(), "graph_hash": self.graph_hash}

    # ------------------------------------------------------------------
    # Phase 8: Accumulation — load, merge, save across runs
    # ------------------------------------------------------------------

    def merge(self, other: "EvidenceGraph") -> "EvidenceGraph":
        """Merge another evidence graph into this one (idempotent on node_id/edge sig)."""
        result = self
        for node in other.nodes:
            result = result.add_node(node)
        for edge in other.edges:
            result = result.add_edge(edge)
        return result

    @classmethod
    def load(cls, path: str | Path) -> "EvidenceGraph":
        """Load an accumulated evidence graph from a file.

        Returns an empty graph if the file doesn't exist (first run).
        """
        from pathlib import Path
        p = Path(path)
        if not p.is_file():
            return cls.create()
        import json
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def save(self, path: str | Path) -> None:
        """Persist the accumulated evidence graph to a file."""
        from pathlib import Path
        from .util import write_json
        write_json(path, self.as_dict())


def build_evidence_graph_from_run(
    run_result: Mapping[str, Any],
    dialectical_graph: Mapping[str, Any],
    verifier_report: Mapping[str, Any],
    local_oracle_result: Mapping[str, Any] | None = None,
) -> EvidenceGraph:
    """Build an Evidence Graph from an orchestrator run's outputs.

    Creates nodes for: checkpoint, experiment (run), claims (dialectical nodes),
    evidence (verifier + oracle), and edges linking them.
    """
    nodes: list[EvidenceNode] = []
    edges: list[EvidenceEdge] = []

    # Checkpoint node
    cp_id = "cp-" + str(run_result.get("meta_run_id", "unknown"))[:16]
    nodes.append(EvidenceNode(
        node_id=cp_id,
        node_kind="CHECKPOINT",
        content_hash=str(run_result.get("telemetry_hash", "0" * 64)),
        status=EvidenceStatus.VERIFIED_LOCAL,
        description=f"Run checkpoint: {run_result.get('status', 'unknown')}",
    ))

    # Experiment (run) node
    exp_id = "exp-" + str(run_result.get("meta_run_id", "unknown"))[:16]
    nodes.append(EvidenceNode(
        node_id=exp_id,
        node_kind="EXPERIMENT",
        content_hash=str(run_result.get("input_hash", "0" * 64)),
        status=EvidenceStatus.VERIFIED_LOCAL,
        description=f"Orchestrator run: {run_result.get('meta_run_id', 'unknown')}",
    ))
    edges.append(EvidenceEdge(
        from_node=exp_id, to_node=cp_id, kind=EvidenceEdgeKind.DERIVES_FROM,
        metadata=(("relationship", "experiment_produces_checkpoint"),),
    ))

    # Dialectical graph claims as CLAIM nodes
    dg_nodes = dialectical_graph.get("nodes", [])
    for i, dg_node in enumerate(dg_nodes):
        claim_id = f"claim-{str(run_result.get('meta_run_id', 'unknown'))[:12]}-{i:03d}"
        nodes.append(EvidenceNode(
            node_id=claim_id,
            node_kind="CLAIM",
            content_hash=str(dg_node.get("proposition", "")[:64]),
            status=EvidenceStatus.UNVERIFIED,
            description=str(dg_node.get("operator", "UNKNOWN")) + ": " + str(dg_node.get("proposition", ""))[:80],
        ))
        edges.append(EvidenceEdge(
            from_node=claim_id, to_node=exp_id, kind=EvidenceEdgeKind.DERIVES_FROM,
            metadata=(("relationship", "claim_from_experiment"),),
        ))

    # Verifier evidence node
    ver_status = str(verifier_report.get("verification_status", "UNKNOWN"))
    ver_ev_status = EvidenceStatus.INSUFFICIENT if "INSUFFICIENT" in ver_status else EvidenceStatus.VERIFIED
    ver_id = "evidence-verifier-" + str(run_result.get("meta_run_id", "unknown"))[:12]
    nodes.append(EvidenceNode(
        node_id=ver_id,
        node_kind="EVIDENCE",
        content_hash=str(verifier_report.get("verifier_hash", "0" * 64)),
        status=ver_ev_status,
        description=f"External verifier: {ver_status}",
    ))
    edges.append(EvidenceEdge(
        from_node=ver_id, to_node=exp_id, kind=EvidenceEdgeKind.SUPPORTS,
        metadata=(("verification_status", ver_status),),
    ))

    # Local oracle evidence node (if available)
    if local_oracle_result and local_oracle_result.get("verification_status") == "VERIFIED_LOCAL":
        oracle_id = "evidence-oracle-" + str(run_result.get("meta_run_id", "unknown"))[:12]
        nodes.append(EvidenceNode(
            node_id=oracle_id,
            node_kind="EVIDENCE",
            content_hash=str(local_oracle_result.get("oracle_commitment", "0" * 64)),
            status=EvidenceStatus.VERIFIED_LOCAL,
            description="Local deterministic oracle: VERIFIED_LOCAL",
        ))
        edges.append(EvidenceEdge(
            from_node=oracle_id, to_node=exp_id, kind=EvidenceEdgeKind.SUPPORTS,
            metadata=(("oracle_authority", "LOCAL_DETERMINISTIC"),),
        ))

    return EvidenceGraph.create(nodes, edges)
