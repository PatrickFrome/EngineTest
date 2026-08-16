# Destruktion 4.0 — Project Development Report 0.7

## Revision thesis

Version `0.7.0-alpha.1` attacks the central residual left by 0.6: **operator inflation**. A source-forced method that only learns can become a larger closed system than the method it replaced. The 0.7 revision therefore adds a second direction of methodological change: the engine must be able to retain, quarantine, revise or retire an experimental operator after preregistered cross-corpus regression.

The architectural loop is now:

`source resistance → representation failure → operator candidate → rival local profiles → cross-corpus regression → retain / revise / quarantine / retire`.

This does not make operator selection self-validating. The cross-corpus result remains an internal engineering/hermeneutic regression with an explicit claim ceiling and never promotes a candidate into frozen CORE.

## Cross-lingual source centrality

The 0.6 source-centrality detector still contained a hidden Heidegger/German prior: it over-weighted capitalized and German-looking technical forms. Version 0.7 replaces that mechanism with Unicode source-frequency + source-document-frequency centrality, a conservative multilingual stop layer and removal of URL/citation noise before term scoring. Explicit ETY stress terms remain optional hints rather than a prerequisite for discovering source-native concepts.

Regression tests now verify that a French Saussure dossier can surface `langue`, `système`, `valeur` and `différences` without an explicit etymological stress list. A Descartes dossier remains source-resistant at the topic level but does not thereby activate the relation-genesis operator.

## Relation profiles instead of one relation ontology

The Geviert-derived operator is no longer interpreted as a preference for co-constitution. Its experimental profile can discriminate among:

- `RELATA_FIRST`;
- `ASYMMETRIC_DEPENDENCE`;
- `RECIPROCAL_RELATION`;
- `CO_CONSTITUTIVE`;
- `RELATION_FIRST`;
- `UNRESOLVED_ONTOLOGY`;
- `LOCAL_PROFILE_VARIATION`.

A source can therefore trigger relation-sensitive analysis while defeating relation-first ontology. This is essential in the Spinoza control, where mode/substance dependence is asymmetric, and in the Aristotle control, where primary-substance priority and relatives require different local profiles inside one corpus.

Geviert additionally activates `DIFFERENCE_PRESERVING_PROXIMITY`: gathering/co-belonging and near/far language jointly support a representational experiment without converting that experiment into an ontological verdict.

## Ancient-source portability fix

The cross-corpus run exposed a non-philosophical but consequential bias: `docx_job.schema.json` and `source_manifest.schema.json` required publication years `>= 1`, making BCE corpora structurally inadmissible. Both schemas now admit integer astronomical-style bibliographic years from `-9999` to `9999`, excluding year `0`. A regression test fixes the Aristotle case.

This is an example of the same project principle at the infrastructure level: a resistant corpus may reveal that the admission schema, not the source, is malformed.

## Operator evolution regression

A new CLI command is available:

`destruktion operator-regression <manifest.json> --out <new-directory>`

The preregistration manifest assigns corpora to four roles:

- `ORIGIN_POSITIVE`;
- `TRANSFER_POSITIVE`;
- `MIXED_CONTROL`;
- `NEGATIVE_CONTROL`.

The result can be:

- `SURVIVES_CROSS_CORPUS_REGRESSION` → `EXPERIMENTAL_TRANSFERABLE`;
- `QUARANTINE_OVERGENERALIZATION` → `QUARANTINED`;
- `RETIRE_NO_TRANSFER` → `RETIRED`;
- `REVIEW_MIXED` → `EXPERIMENTAL_UNRESOLVED`.

The recommended action is serialized. No outcome is `CORE_PROMOTED`.

## Five-corpus adversarial benchmark

The candidate under test was `RELATION_GENESIS_PROFILE_WITH_CO_EMERGENT_RELATA_CANDIDATE`.

| Corpus | Role | Source-central terms | Relation profile | Candidate mutation |
|---|---|---:|---|---|
| Heidegger — Geviert | ORIGIN_POSITIVE | 14 | reciprocal/co-constitutive + difference-preserving proximity | yes |
| Saussure — valeur/différence/système | TRANSFER_POSITIVE | 5 | differential constitution | yes |
| Spinoza — substance/mode | MIXED_CONTROL | 5 | asymmetric dependence | yes |
| Aristotle — substance/relatives | MIXED_CONTROL | 6 | asymmetric dependence + local mode variation | yes |
| Descartes — cogito | NEGATIVE_CONTROL | 5 | generic source-forced revision, no relation-genesis profile | no |

All five preregistered expectations passed. The result is:

`SURVIVES_CROSS_CORPUS_REGRESSION`

with state:

`EXPERIMENTAL_TRANSFERABLE`

and action:

`RETAIN_EXPERIMENTAL_FOR_FURTHER_REGRESSION`.

This is deliberately weaker than acceptance into the project ontology. One positive transfer and two mixed controls show discrimination under this benchmark; they do not establish a universal relation-genesis theory.

## Why this increases hermeneutic nonlinearity

The key gain is not that the graph became larger. The engine can now traverse **different local relation regimes without requiring one global ontology of relation**. Saussure can be differential without becoming Geviert; Spinoza can be dependent without becoming reciprocal; Aristotle can require multiple local profiles; Descartes can remain outside the relation-genesis candidate entirely.

Thus nonlinearity shifts from “many paths through one ontology” toward “a revisable ecology of locally discriminated representational commitments.”

## Why this increases epistemic nonlinearity

The engine now separates four judgments that previously risked collapsing:

1. a source is poorly represented by the current registry;
2. an experimental operator is generatively useful on the origin corpus;
3. the operator transfers with discriminating gain;
4. the operator is philosophically true.

Only the first three are tested here. The fourth remains outside the regression claim ceiling.

The lifecycle also introduces negative epistemic learning. A candidate can be made less available by quarantine or removed from experimental default routing by retirement. “Learning” is therefore no longer synonymous with accumulating categories.

## Remaining risks

The main unresolved risks are now different from 0.6:

- lexical source-centrality still approximates conceptual centrality and can miss hapax-like decisive terms;
- signal families remain engineered heuristics and may encode hidden language/domain priors;
- the current regression tests one candidate family rather than genuinely competing newly generated operator families;
- `EXPERIMENTAL_TRANSFERABLE` is not yet a runtime policy that automatically changes future routing; the regression emits governance advice but does not silently rewrite frozen configuration;
- external expert semantic validation remains pending.

The strongest next stage is therefore **operator competition** rather than another transfer test: two or more source-forced operator candidates should compete on the same corpus under explicit loss/gain criteria, with the ability to compose locally, remain unresolved, or be retired.

## Release ceiling

`0.7.0-alpha.1` is a developer-tested research alpha. Structural conformance, internal cross-corpus regression, source-centrality detection, ETY coverage and method-mutation traces are not external semantic validation. `CORE 4.0.0-alpha.1` remains unchanged.
