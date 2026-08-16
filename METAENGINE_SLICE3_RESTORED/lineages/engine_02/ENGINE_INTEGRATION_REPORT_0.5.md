# Destruktion 4.0 — Engine Integration Report 0.5

## 1. Scope

This release merges the verified engine line `0.9.0-alpha.1` with the external reflective Studio line developed through `Studio 0.4`. The merge is deliberately asymmetric:

- the 0.9 engine becomes the new **frozen executable baseline**;
- Studio remains an external experimental/reflexive layer;
- no Studio feature is allowed to silently rewrite the 48 assets bound by `PORTABLE_PROJECT.json`;
- source-resistance discovery, operator mutation, regression and local ecology remain separated by explicit promotion firewalls.

The supplied micro-local regression archive was also audited against the portable 0.9 archive. All 9 overlapping files are byte-identical; its only additional file is `REPLAY.md`.

## 2. Strong 0.9 solutions accepted

### 2.1 Bundled offline structural validator

`src/structural-validator.mjs` first uses pinned `ajv@8.17.1` when installed and otherwise falls back to `vendor/ajv-compat/2020.mjs`.

**Why accepted:** Studio 0.4 still treated missing npm AJV as a runtime blocker. The 0.9 fallback removes that dependency from the critical portable path while preserving schema validation. The complete 0.9 suite passed without `node_modules`.

**Integration:** Studio `doctor` now regards either pinned AJV or the bundled compatibility validator as a valid backend. `setup` may try `npm ci`, but an unavailable registry no longer makes an otherwise conformant offline project unusable.

### 2.2 Source-forced resistance rather than developer-forced novelty

`src/source-resistance.mjs` identifies source-native centrality and relation-genesis pressure rather than treating explicit project theses or manually preferred concepts as sufficient grounds for method mutation.

**Why accepted:** this moves novelty pressure toward the source and away from ritual “surprise generation”. It is especially valuable for the project’s epistemic nonlinearity because the source can force a topic/operator outside the curated registry.

**Boundary retained:** source centrality is a detector of representational pressure, not proof of philosophical meaning.

### 2.3 GX7 — representation failure as a first-class generative gesture

0.9 adds the chain:

`SOURCE_RESISTANCE → REPRESENTATION_FAILURE → OPERATOR_DELTA`

with `GG7_OPERATOR_EVOLUTION` and an explicit `EXPERIMENTAL_CANDIDATE_NOT_CORE` mutation state.

**Why accepted:** this is the strongest bridge between analysis and self-critique in 0.9. The engine can represent the possibility that its own ontology of units/relations is part of the failure.

**Integration:** GX7 is now also expressed in `config/living_operator_registry.declarative.json` and executed by the generic declarative gesture interpreter. The declarative schema was upgraded to cover method-mutation nodes, `FORCES_MUTATION`, the new openness criterion and the 0.9 mutation envelope.

### 2.4 Cross-corpus operator regression with negative and mixed controls

`src/operator-regression.mjs` preregisters corpus roles (`ORIGIN_POSITIVE`, `TRANSFER_POSITIVE`, `MIXED_CONTROL`, `NEGATIVE_CONTROL`) and can retain, quarantine, retire or leave an operator unresolved.

**Why accepted:** a source-born operator must survive outside its birth case without firing indiscriminately. The presence of an explicit negative control is a major improvement over accumulation-only development.

**Boundary retained:** `EXPERIMENTAL_TRANSFERABLE` is not CORE promotion and not external semantic validation.

### 2.5 Local operator competition with composition and abstention

`src/operator-competition.mjs` can produce `SELECT_LOCAL_WINNER`, `LOCAL_COMPOSITION`, `KEEP_RIVALS_UNRESOLVED`, or `ABSTAIN_UNRESOLVED`.

**Why accepted:** it prevents the project from assuming that every conflict has one globally best operator. Composition is local and abstention is a legitimate outcome.

**Boundary retained:** competition scores are routing heuristics, not truth values.

### 2.6 Micro-local operator ecology and localization-loss audit

`src/micro-local-operator-ecology.mjs` routes provenance-bound windows independently, preserves operator boundaries and audits the loss caused by global synthesis.

The supplied Aristotle regression produces four micro-windows, preserves two operator boundaries, leaves one boundary unresolved, includes one abstention, and detects four instances of localization loss. The correct synthesis is:

`REJECT_GLOBAL_COLLAPSE_PRESERVE_WINDOW_PROVENANCE`

**Why accepted:** this is one of the strongest mechanisms in the current project for hermeneutic nonlinearity. Different parts of the same work may require different operators without being forced into a single meta-ontology.

### 2.7 Chronological schema portability

The 0.9 schema fixes year-domain assumptions so BCE corpora can be represented without an artificial modern-year bias or year zero.

**Why accepted:** this is a small but important portability correction for historical/genealogical research.

## 3. Studio mechanisms retained and connected to 0.9

### Operator Mutation Engine

Studio’s reversible `operator_delta` gate remains the promotion firewall. A GX7 method mutation from the 0.9 engine is a candidate/evidence source, not a bypass around this gate.

### Declarative Generative Gesture Runtime

GX1–GX7 can now be interpreted as data. A new gesture variant can be tested without adding gesture-id-specific JavaScript dispatch.

### A/B/C Comparator

Frozen baseline, declarative baseline and accepted declarative mutant remain separately runnable. Structural change is reported without converting “more nodes” or “more complexity” into a quality score.

### Resistant-Source Discovery Engine

Studio discovery now treats `SOURCE_RESISTANCE`, `REPRESENTATION_FAILURE` and `OPERATOR_DELTA` as explicit pressure signals. Longitudinal recurrence remains evidence for review only; discovered delta seeds cannot promote themselves.

## 4. Integration decisions: adapted rather than copied

1. **GX7 is dual-runtime.** The 0.9 frozen executor remains intact, while an equivalent declarative GX7 is maintained outside the frozen baseline.
2. **0.9 method mutation does not self-promote.** Its candidate must still pass source review, Studio mutation gate and regression.
3. **Cross-corpus survival is not universality.** Transfer can retain an operator experimentally but cannot erase local boundaries.
4. **Competition cannot decide meaning.** The scoring layer only routes source-born candidates under preregistered expectations.
5. **Micro-local windows dominate global convenience.** If global synthesis creates localization loss, the integrated policy preserves the window-level ecology.
6. **Developer-authored profile hints remain hypotheses/preregistration aids.** They are not upgraded into source-semantic evidence merely because a test expectation matches them.

## 5. Explicitly rejected shortcuts

The merge does **not** introduce:

- automatic CORE promotion from source resistance;
- automatic promotion from cross-corpus regression;
- mutation acceptance by the same discovery mechanism that proposed it;
- “highest score = philosophical truth” logic;
- forced global synthesis across incompatible local operators;
- silent replacement of the 0.9 frozen registry by Studio’s declarative registry;
- novelty or node count as an epistemic quality metric.

## 6. End-to-end integration result

A real Geviert refinery was executed through the integrated declarative runtime. The run:

- validated with zero schema errors;
- activated GX7;
- emitted `SOURCE_RESISTANCE`, `REPRESENTATION_FAILURE`, and `OPERATOR_DELTA` nodes;
- emitted exactly one `method_mutations` candidate;
- kept that mutation in `EXPERIMENTAL_CANDIDATE_NOT_CORE` state;
- satisfied the explicit source-resistance openness criterion.

This end-to-end run exposed and led to the repair of four schema/runtime mismatches that unit tests alone had missed. The case is now part of the permanent Studio regression suite.

## 7. Resulting architecture

```text
SOURCE / CORPUS
      │
      ├─ source centrality / relation pressure
      │           │
      │           └─ GX7 source resistance
      │                 ↓
      │        representation failure
      │                 ↓
      │        experimental operator delta
      │                 ↓
      ├──────── Studio review / mutation gate ────────┐
      │                                               │
      │                                      accepted candidate
      │                                               ↓
      ├─ cross-corpus regression ←──────────── experimental operator
      │       ├─ retain
      │       ├─ quarantine
      │       ├─ retire
      │       └─ unresolved
      │
      ├─ local operator competition
      │       ├─ winner
      │       ├─ composition
      │       ├─ rivals unresolved
      │       └─ abstain
      │
      └─ micro-local ecology
              ├─ provenance-bound windows
              ├─ operator boundaries
              ├─ localization-loss audit
              └─ reject global collapse when necessary

Longitudinal Studio discovery observes this history but cannot self-promote.
```

## 8. Assessment

The most important gain is not that 0.9 adds “more operators”. It adds **retirement, negative controls, abstention, locality and representation-failure feedback**. Those mechanisms make the system less accumulative and less teleological. The integrated engine is therefore stronger precisely where it can refuse to generalize, preserve incompatible local regimes, and make its own representational failure an object of controlled revision.
