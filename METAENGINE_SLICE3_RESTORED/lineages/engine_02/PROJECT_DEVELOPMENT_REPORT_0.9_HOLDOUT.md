# Destruktion 4.0 — Project Development Report 0.9

## Stage: Frozen Passage Holdout

The previous 0.8 release built the anti-self-confirmation and external-comparison envelope but contained only a 22-unit real scaffold, below the frozen minimum of 80. Studio 0.9 addresses that specific weakness without adding a new GX, operator family, or mutation type.

### Architectural change

The project now distinguishes two empirical tasks:

- **CORE expert-status benchmark** — evaluates terminal `SUPPORTED / QUALIFIED / REJECTED / INSUFFICIENT` decisions produced by ordinary expert cycles.
- **Passage architecture holdout** — evaluates whether the three strongest Destruktion architectural moves are warranted on preselected passages.

The latter uses 27 deterministic passages and exactly three fixed hypotheses per passage. This avoids the category error of fabricating ordinary `expert_cycle` records merely to reach a sample-size threshold.

### Why this is stronger than adding another mechanism

Before 0.9, most tests asked whether Destruktion implemented its own contracts. The new holdout creates an externally judgeable sample where the engine can be wrong in several informative ways:

- relation-genesis can overfire on generic relational vocabulary;
- processual-hermeneutic signals can overfire on ordinary temporal/action language;
- open-set discovery can miss a genuinely unserved distinction;
- open-set discovery can invent novelty from recurrence or lexical noise;
- `INSUFFICIENT` can be overused as safe abstention;
- `SUPPORTED` can encode trigger density rather than hermeneutic gain.

### Embargo

The 27 passages are now evaluation material. They must not be used for tuning until the primary gold and comparison are frozen. If the project is modified from errors found here, the next empirical claim requires a new holdout rather than reusing 0.9 as if it were unseen.

### Current epistemic status

`SIZE_GATE_READY / BLOCKED_PENDING_INDEPENDENT_LABELS`

That blocking status is the intended outcome of this stage.
