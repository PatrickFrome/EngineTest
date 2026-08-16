# Destruktion 4.0 — Engine Integration Report 0.6

## Scope

Integrated source engine: `Destruktion_4.0_AI_CHAT_PORTABLE_0.10.0-alpha.1`.

Verified uploaded ZIP SHA-256:

`cf78f697616b32bf399bf8f43eb15ecd0fa0031e4b2115c09629cef3493f5202`

The supplied checksum matched exactly.

The integration uses 0.10.0-alpha.1 as the new **frozen engine baseline** and places Studio adaptation outside its 66 cryptographically bound required assets.

## Executive assessment

0.10 is a genuine architectural advance over the 0.9 engine line. Its strongest contribution is not another named operator, but a transition from a closed operator vocabulary to an experimentally open one:

`REGISTRY_BLIND_SPOT → UNKNOWN_OPERATOR_FAMILY → ADD_OPERATOR → executable candidate registry`

This closes an important loop in the Destruktion project. Source resistance no longer has to be translated immediately into an existing family such as difference, dependence, reciprocity or relation-first. A source-central field can remain an unresolved rival and can generate a reversible executable operator candidate.

The advance is real because the candidate is not metadata-only. In the supplied controlled regression the new F-OPEN family changes the living graph.

At the same time, 0.10 remains semantically underpowered at the discovery boundary. Its novelty detector is primarily recurrence/co-occurrence based. It does not yet robustly distinguish assertion from negation, authorial position from quotation/opponent attribution, or semantic persistence from surface terminology. For that reason this integration accepts open-set birth but adds a Studio-level semantic-review debt before any CORE or universalization claim.

## Strong solutions accepted directly

### 1. Open-set hermeneutic discovery

Accepted: `src/open-set-discovery.mjs` and its source-resistance integration.

Strong properties:

- does not require every blind spot to resolve into the known operator registry;
- produces deterministic candidate IDs tied to a source signature;
- retains rival unitizations rather than one compulsory interpretation;
- keeps explicit claim ceiling `OPEN_SET_OPERATOR_CANDIDATE_NOT_DISCOVERED_ONTOLOGY_OR_CORE_PROMOTION`;
- uses local argument windows instead of corpus-wide first-pass totalization;
- includes `ABSTAIN_LOCAL` as a valid route.

### 2. `ADD_OPERATOR`

Accepted: mutation-engine and schema support for `ADD_OPERATOR`.

Strong properties:

- new conditional family is added only to a candidate registry;
- frozen baseline registry remains unchanged;
- duplicate IDs are rejected;
- runtime reachability must be `FULL`;
- executable before/after probe must actually change behavior;
- rollback for operator birth is explicit removal of the added operator;
- same-source fixture, GG1 gain, traceability and negative gates remain in force.

This is a stronger form of operator mutation than merely revising or splitting a known family because it allows the vocabulary itself to expand without pretending the expansion is already validated.

### 3. Declarative runtime 1.1

Accepted as the main living runtime.

The 0.10 baseline registry itself is now declarative (`DAE-LIVING-DECLARATIVE-1.1`). GX1–GX7 activation and emission can be interpreted by the generic runtime. Consequently a generative-gesture revision that was only partially reachable in earlier Studio assumptions is now fully executable when it remains inside the declarative contract.

### 4. Open-set micro-local routing

Accepted as a new routing layer.

Local outcomes:

- `KNOWN_PROFILE_LOCAL`
- `OPEN_SET_LOCAL_CANDIDATE`
- `KEEP_KNOWN_AND_OPEN_SET_RIVALS`
- `ABSTAIN_LOCAL`

This is useful because known and unknown families can coexist as rivals inside the same source rather than forcing one global operator choice.

### 5. Portable/offline integrity

Accepted unchanged.

0.10 ships 66 cryptographically bound assets and a bundled AJV-compatible structural-validator fallback. The complete engine test suite executes in the current sandbox without installing npm AJV.

## Strong 0.9 solution deliberately preserved

The 0.10 file named `micro-local-ecology.mjs` does not perform the same audit as the previous 0.9 `micro-local-operator-ecology` regression. The new component routes known/open-set candidates per window, but the old component asks a different and stronger question:

> If all locally selected operators are composed globally, which windows acquire operators for which they had no local warrant?

Therefore the 0.9 localization-loss audit was **not overwritten**.

Studio 0.6 exposes both:

```bash
node studio/studio.mjs ecology:open-set <hypothesis_bank.json> --out <dir>
node studio/studio.mjs ecology:regression <micro_local_operator_ecology_manifest.json> --out <dir>
```

The preserved regression fixture returns four localization-loss pairs and:

`REJECT_GLOBAL_COLLAPSE_PRESERVE_WINDOW_PROVENANCE`

This combination is stronger than either implementation alone:

`open-set local routing` answers **what may compete here?**

`localization-loss regression` answers **what would be falsely universalized if local decisions were collapsed?**

## Studio adaptations

### A. Frozen 0.10 baseline

The new engine baseline is not patched in place. All 66 required assets pass their original SHA-256 checks.

Studio additions live outside that cryptographic set.

### B. A/B/C comparator redefined

The old comparison `legacy baseline → declarative baseline → mutant` became redundant because 0.10 itself is declarative.

Studio 0.6 therefore uses:

1. **A — historical 0.9 registry control**;
2. **B — frozen 0.10 open-set baseline**;
3. **C — accepted 0.10 mutant candidate**.

On the supplied Descartes open-set refinery with one shared seed:

- historical 0.9: 3 constellations / **100 nodes / 148 edges**;
- frozen 0.10: 3 constellations / **101 nodes / 149 edges**;
- open-set mutant: 3 constellations / **104 nodes / 153 edges**.

Comparator result:

- `mutation_effect_observed=true`;
- structural diversity `3/3`.

This does **not** mean the mutant is philosophically better. It proves only that the operator birth is behaviorally non-trivial and distinguishable from both historical and current baselines.

### C. Explicit registry injection

Studio mutant runs now use the 0.10 native `living-cycle --registry <candidate>` interface rather than relying on legacy process-environment injection. This removes a hidden compatibility dependency and makes candidate execution directly auditable in command logs.

### D. Runtime-version compatibility

Studio no longer hard-codes exactly `DAE-LIVING-DECLARATIVE-1.0`; it recognizes the declarative runtime family and therefore works with 1.1 and later compatible revisions.

### E. Open-set semantic-review debt

The engine correctly labels open-set candidates as experimental, but its mutation receipt can still say `promotion_ready=true`, meaning ready to become an executable candidate registry. That phrase can be misread as semantic or CORE promotion.

Studio therefore annotates every promoted `ADD_OPERATOR` candidate with:

`open_set_semantic_review.status = REQUIRED_BEFORE_ANY_CORE_OR_UNIVERSALIZATION_CLAIM`

Required future semantic axes:

1. predicate and polarity;
2. authorial attribution / quoted-opponent separation;
3. modality;
4. argumentative role;
5. paraphrase / translation perturbation;
6. decoy terminology and negation controls.

Experimental execution remains allowed. CORE or universalization interpretation does not.

## Weaknesses of 0.10 not silently adopted as strengths

### 1. Recurrence is not semantic role

A term can recur because an author rejects it, quotes an opponent, stages a reductio, gives an example, or repeats a translation convention. Co-occurrence alone cannot distinguish these cases.

### 2. Candidate naming can overfit lexical surface

`F-OPEN-<TERMS>-<HASH>` is reproducible but can make the candidate appear more semantically determinate than it really is. The ID is treated as a traceable handle, not a concept discovered in the source.

### 3. Windowing is intentionally crude

The current open-set window builder uses small contiguous source runs and bounded width/count. It is effective as a pressure detector, not as a complete theory of argumentative segmentation.

### 4. Negative boundaries remain dangerous

`U-NEGATIVE-BOUNDARY` is useful as a rival hypothesis, but absence/co-occurrence breakage can easily be reified. It remains provisional and receives no automatic metaphysical interpretation.

### 5. `promotion_ready` is only an engineering gate

It means the candidate is reversible, executable, source-bound and has passed the encoded mutation checks. It does not mean the operator is true, externally validated, transferable, philosophically adequate or eligible for CORE status.

### 6. Local routing and local validity are different

A route transition shows that the machine changed representation. It does not establish that the source itself contains a corresponding ontological transition.

## Integrated architecture

```text
SOURCE
  │
  ├─ source centrality / registry coverage
  │
  ▼
REGISTRY_BLIND_SPOT
  │
  ├──────── known profile remains available
  │
  ▼
UNKNOWN_OPERATOR_FAMILY
  │
  ├─ rival unitizations
  ├─ micro-local windows
  └─ ABSTAIN possible
  │
  ▼
ADD_OPERATOR delta
  │
  ▼
Studio mutation gate
  │
  ├─ reject/review
  │
  ▼
ACCEPTED_CANDIDATE
  │
  ├─ semantic-review debt for open-set births
  ├─ A/B/C historical/current/mutant comparison
  ├─ cross-corpus regression
  ├─ operator competition
  └─ retirement/quarantine/abstention
  │
  ▼
open-set local routing
  │
  ▼
0.9 localization-loss audit
  │
  ├─ preserve local provenance
  └─ reject global collapse when warranted
```

## Result

The integration increases epistemic and hermeneutic nonlinearity in a controlled way. The key gain is not that the project has more operators; it is that the project can now state:

> the existing vocabulary may be the failure, and the source may require an operator that does not yet exist.

Equally important, the integrated version retains mechanisms that can answer:

> the newly born operator may be only a lexical hallucination, may fail elsewhere, may lose to a rival, may need quarantine, may remain local, or may need retirement.

That combination — vocabulary openness plus reversible self-limitation — is the strongest contribution of the 0.10 merge.
