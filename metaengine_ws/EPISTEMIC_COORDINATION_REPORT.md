# Epistemic Coordination Layer 1.1

## Purpose

The 1.0 engine proved synchronized 16-way execution. Its main remaining weakness was meta-level: all contributions were retained, but the architecture did not yet formalize *which claim each contribution bears on*, *where engines materially disagree*, or *why a claim may or may not be promoted*. 1.1 implements that missing layer.

## Four kernels

### Capability Router
Deterministic task fingerprinting maps input signals to capability relevance. Roles are adaptive, membership is not: FULL_16X always schedules all sixteen.

### Claim Graph
Positions retain engine provenance, source refs, force, evidence kind/strength and claim ceiling. Aggregation is structural only. Generative outputs cannot silently become evidence.

### Disagreement Engine
Material stance conflict is a first-class research object. Tension and priority allocate future attention; disagreement is not a fusion failure.

### Adaptive Arbitration
Promotion depends on source grounding and absence of unresolved material conflict. Simple majority is prohibited. A dissenting lineage remains visible even when numerically isolated.

## Smoke evidence

The synchronized sample run completed 16/16 primary + 16/16 cross-review and generated `ROUTING_PLAN.json`, `CLAIM_GRAPH.json`, `DISAGREEMENT_MAP.json`, `ARBITRATION.json`, `PRIMARY_FUSION.json`, and `FINAL_FUSION.json`. The sample produced 27 claim nodes / 43 positions and zero material conflicts; the system did not fabricate tension.

## Adversarial evidence

`ADVERSARIAL_ARBITRATION_REPORT.md` records the 3:1 dissent regression. Majority voting is explicitly serialized as unused.

## Remaining limit / next gate

1.1 routing is deterministic and hand-designed; engine specialization is not yet learned from longitudinal outcome history. Claim equivalence is conservative and does not yet perform semantic entailment. The next stage should therefore be **1.2 — Engine Specialization Memory + Empirical Reliability Profiles**, using run history to learn where each lineage adds unique value, fails, abstains, or catches errors that others miss—without allowing correlated lineages to manufacture false confidence.
