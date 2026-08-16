"""METAENGINE Phase 3 — Evidence Graph tests."""

from __future__ import annotations

import pytest

from metaengine.evidence_graph import (
    EvidenceGraph,
    EvidenceNode,
    EvidenceEdge,
    EvidenceEdgeKind,
    EvidenceStatus,
    build_evidence_graph_from_run,
    EVIDENCE_GRAPH_VERSION,
)


# ---------------------------------------------------------------------------
# EvidenceNode / EvidenceEdge
# ---------------------------------------------------------------------------


def test_node_create_and_payload():
    n = EvidenceNode(node_id="test-1", node_kind="CLAIM", content_hash="a" * 64, status=EvidenceStatus.UNVERIFIED, description="test")
    p = n.payload()
    assert p["node_id"] == "test-1"
    assert p["status"] == "UNVERIFIED"


def test_edge_create_and_payload():
    e = EvidenceEdge(from_node="a", to_node="b", kind=EvidenceEdgeKind.SUPPORTS, metadata=(("k", "v"),))
    p = e.payload()
    assert p["kind"] == "SUPPORTS"
    assert p["metadata"] == [["k", "v"]]


# ---------------------------------------------------------------------------
# EvidenceGraph
# ---------------------------------------------------------------------------


def test_empty_graph():
    g = EvidenceGraph.create()
    assert len(g.nodes) == 0
    assert len(g.edges) == 0
    assert g.graph_hash


def test_graph_hash_deterministic():
    n = EvidenceNode(node_id="n1", node_kind="CLAIM", content_hash="a" * 64, status=EvidenceStatus.UNVERIFIED, description="t")
    g1 = EvidenceGraph.create(nodes=[n])
    g2 = EvidenceGraph.create(nodes=[n])
    assert g1.graph_hash == g2.graph_hash


def test_add_node():
    g = EvidenceGraph.create()
    n = EvidenceNode(node_id="n1", node_kind="CLAIM", content_hash="a" * 64, status=EvidenceStatus.UNVERIFIED, description="t")
    g = g.add_node(n)
    assert len(g.nodes) == 1


def test_add_node_idempotent():
    g = EvidenceGraph.create()
    n = EvidenceNode(node_id="n1", node_kind="CLAIM", content_hash="a" * 64, status=EvidenceStatus.UNVERIFIED, description="t")
    g = g.add_node(n).add_node(n)
    assert len(g.nodes) == 1


def test_add_edge():
    g = EvidenceGraph.create(nodes=[
        EvidenceNode(node_id="a", node_kind="CLAIM", content_hash="a" * 64, status=EvidenceStatus.UNVERIFIED, description=""),
        EvidenceNode(node_id="b", node_kind="EVIDENCE", content_hash="b" * 64, status=EvidenceStatus.VERIFIED, description=""),
    ])
    e = EvidenceEdge(from_node="a", to_node="b", kind=EvidenceEdgeKind.SUPPORTS, metadata=())
    g = g.add_edge(e)
    assert len(g.edges) == 1


def test_from_dict_revalidates_hash():
    n = EvidenceNode(node_id="n1", node_kind="CLAIM", content_hash="a" * 64, status=EvidenceStatus.UNVERIFIED, description="t")
    g = EvidenceGraph.create(nodes=[n])
    restored = EvidenceGraph.from_dict(g.as_dict())
    assert restored.graph_hash == g.graph_hash


def test_from_dict_rejects_tampered_hash():
    """Step 3: Hash mismatch now warns (not raises) — demoted for schema evolution."""
    n = EvidenceNode(node_id="n1", node_kind="CLAIM", content_hash="a" * 64, status=EvidenceStatus.UNVERIFIED, description="t")
    g = EvidenceGraph.create(nodes=[n])
    tampered = g.as_dict()
    tampered["graph_hash"] = "0" * 64
    # Step 3: Was pytest.raises(ValueError), now warns and returns graph
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = EvidenceGraph.from_dict(tampered)
        assert len(w) == 1
        assert "EVIDENCE_GRAPH_HASH_MISMATCH" in str(w[0].message)
    assert result is not None  # Graph is still returned


# ---------------------------------------------------------------------------
# build_evidence_graph_from_run
# ---------------------------------------------------------------------------


def test_build_from_run():
    run = {"meta_run_id": "meta23-test", "input_hash": "a" * 64, "telemetry_hash": "b" * 64, "status": "COMPLETE"}
    dg = {"nodes": [{"operator": "SOURCE_READING", "proposition": "test claim"}]}
    verifier = {"verification_status": "INSUFFICIENT_EXTERNAL_EVIDENCE", "verifier_hash": "c" * 64}
    oracle = {"verification_status": "VERIFIED_LOCAL", "oracle_commitment": "d" * 64}

    g = build_evidence_graph_from_run(run, dg, verifier, oracle)

    assert len(g.nodes) >= 4  # checkpoint + experiment + verifier + oracle
    assert len(g.edges) >= 4
    assert g.graph_hash
    # Must have claim_ceiling and truth_effect
    p = g.payload()
    assert p["claim_ceiling"] == "EVIDENCE_GRAPH_ACCUMULATES_KNOWLEDGE_NOT_TRUTH"
    assert p["truth_effect"] == "NONE"


def test_build_without_oracle():
    run = {"meta_run_id": "meta23-test2", "input_hash": "a" * 64, "telemetry_hash": "b" * 64, "status": "COMPLETE"}
    dg = {"nodes": []}
    verifier = {"verification_status": "VERIFIED", "verifier_hash": "c" * 64}

    g = build_evidence_graph_from_run(run, dg, verifier)

    # No oracle → no oracle node
    oracle_nodes = [n for n in g.nodes if "oracle" in n.node_id]
    assert len(oracle_nodes) == 0


def test_build_has_claim_nodes_from_dialectical():
    run = {"meta_run_id": "meta23-claims", "input_hash": "a" * 64, "telemetry_hash": "b" * 64, "status": "COMPLETE"}
    dg = {"nodes": [{"operator": "SOURCE_READING", "proposition": "claim1"}, {"operator": "RIVAL_FORK", "proposition": "claim2"}]}
    verifier = {"verification_status": "INSUFFICIENT_EXTERNAL_EVIDENCE", "verifier_hash": "c" * 64}

    g = build_evidence_graph_from_run(run, dg, verifier)

    claim_nodes = [n for n in g.nodes if n.node_kind == "CLAIM"]
    assert len(claim_nodes) == 2
