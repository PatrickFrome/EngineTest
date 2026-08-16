# Destruktion 4.0 — Frozen Passage Holdout Protocol 0.9

## Purpose

Studio 0.9 adds a passage-level external holdout without modifying the 66 frozen CORE 0.10 assets. Its purpose is to test three of the project's strongest architectural claims on passages selected before DAE execution rather than on development/regression fixtures.

This is a project-development holdout, **not** a claim that the underlying language model has never seen these public-domain works during pretraining.

## Frozen sample

- 9 works.
- 3 excerpts per work, centered deterministically at 25%, 50%, and 75% of normalized word position.
- 1,200 words per excerpt.
- 27 excerpts total.
- 3 preregistered architectural hypotheses per excerpt.
- 81 passage×hypothesis units total.

Selection did not use DAE outputs. Exact source and excerpt hashes live in `experiments/external-validation-0.9/HOLDOUT_SOURCE_FREEZE.json`.

## Three fixed hypotheses

1. `RELATION_GENESIS_APPLICABILITY`
2. `PROCESSUAL_HERMENEUTIC_APPLICABILITY`
3. `OPEN_SET_NECESSITY`

The same three hypotheses are applied to every excerpt. No passage receives a custom question chosen after seeing DAE behavior.

## Sources

The holdout uses public-domain Project Gutenberg editions of Plato's *Republic*, Kant's *Critique of Pure Reason*, Nietzsche's *Beyond Good and Evil*, Hume's *Enquiry Concerning Human Understanding*, Berkeley's *Principles of Human Knowledge*, Locke's *Essay Concerning Humane Understanding*, Mill's *On Liberty*, Rousseau's *Social Contract & Discourses*, and Hobbes's *Leviathan*. Exact ebook IDs, URLs, full-source hashes, cleaned-text hashes, excerpt positions, and excerpt hashes are recorded in the source freeze manifest.

## DAE prediction freeze

DAE predictions are produced before human labels. For relation-genesis and processual-hermeneutic hypotheses, the frozen lexical/interrogative signal runtime yields a bounded prediction. For open-set necessity, the prediction is derived from the actual frozen CORE refinery `source_resistance.open_set_status` for the excerpt.

Predictions are stored in `sealed_dae_predictions.json` and excluded from coder packets.

Current frozen prediction distribution:

- `SUPPORTED`: 26
- `QUALIFIED`: 16
- `REJECTED`: 25
- `INSUFFICIENT`: 14

This distribution is **not gold** and is not evidence that the project succeeds.

## Blinding

Two coder packets omit:

- DAE status;
- DAE confidence;
- DAE signal counts;
- open-set runtime state;
- gold labels.

Coders judge whether each architectural hypothesis adds a source-linked distinction, not whether its trigger vocabulary occurs.

## Holdout embargo

Until raw independent annotations, adjudicated gold, and the first primary evaluation are frozen, the holdout passages must not be used to:

- tune relation/processual signal thresholds;
- add or delete lexical triggers;
- create or promote operators;
- create or promote interrogative families;
- change open-set thresholds;
- change mutation gates;
- change passage-selection rules.

A later exploratory phase may use the holdout for error analysis only after the primary result is frozen, and any resulting changes require a new holdout.

## Required next evidence

The release intentionally contains no fabricated gold and no fabricated external-model predictions. Completion requires:

1. two independent coder annotation files;
2. adjudication into frozen gold;
3. at least one strong external comparator frozen before gold is opened;
4. the seven-way semantic adversarial challenge;
5. multi-objective comparison with no scalar global winner.

## Claim ceiling

`FROZEN_HOLDOUT_DESIGN_NOT_EXTERNAL_VALIDATION_RESULT`
