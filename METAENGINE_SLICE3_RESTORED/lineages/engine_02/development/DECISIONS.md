# Architecture decisions — local Studio layer

## ADR-001 — Studio is additive

**Decision:** не изменять обязательные portable-assets и frozen CORE ради удобства запуска. Studio добавляется новыми файлами и рабочими каталогами.

**Reason:** эксплуатационное удобство не должно менять объект валидации или стирать provenance исходного релиза.

## ADR-002 — One run, one directory

**Decision:** каждый запуск получает новую timestamped-папку и собственные копии входного DOCX/job.

**Reason:** результаты living/expert нельзя незаметно перезаписывать при последующем развитии операторов.

## ADR-003 — Operator mutation is scaffold-only

**Decision:** до появления schema + validator + regression gate `operator_delta` в Studio маркируется `PROPOSAL_NOT_ENGINE_CONTRACT`.

**Reason:** не приписывать движку ещё не реализованную способность.

## ADR-004 — Snapshot hashes, not duplicated source trees

**Decision:** snapshot фиксирует SHA-256 активной поверхности вместо полного копирования проекта.

**Reason:** дешёвое сравнение архитектурных состояний без разрастания архива; Git при наличии остаётся предпочтительным для полноценного diff.

## ADR-005 — Mutation changes candidates, not the baseline

**Decision:** accepted `operator_delta` produces a new registry artifact in `workspace/operator-registries`; it never rewrites `config/living_operator_registry.json`.

**Reason:** operator evolution must remain contrastable against the exact operator that failed.

## ADR-006 — Same-source contrast is mandatory

**Decision:** before/after mutation tests must use the same source selector and expose at least two incompatible unitizations.

**Reason:** otherwise an apparent gain can be manufactured by changing the material rather than the operator.

## ADR-007 — Runtime reachability is a promotion gate

**Decision:** a delta cannot be promotion-ready if its registry section is not fully executable by the current living runtime.

**Reason:** declarative edits must not be presented as operative changes when behavior is still hard-coded elsewhere.

## ADR-008 — Mutant registry injection is process-scoped

**Decision:** `src/paths.mjs` may redirect only `config/living_operator_registry.json` when `DESTRUKTION_LIVING_OPERATOR_REGISTRY` is explicitly set for one child process.

**Reason:** this enables real mutant runs while preserving baseline fixity and rollback.

## ADR-009 — Generative gestures are executable data

**Decision:** Studio 0.3 introduces a parallel declarative registry and generic activation/emission interpreter; no new gesture may be considered fully reachable merely because its ID exists in JSON.

**Reason:** resistant-source mutation must be able to alter analytical movement without requiring a hidden second implementation in gesture-specific JavaScript branches.

## ADR-010 — Openness is role-based, not gesture-ID-based

**Decision:** sufficient-openness checks depend on semantic outputs such as `REVERSE_TEST`, `FORMAL_INDICATION` and `REVISION_TRIGGER`, not literal GX identifiers.

**Reason:** a valid split or rename must not accidentally disable the criteria that keep the analysis revisable.

## ADR-011 — Runtime evolution is compared under controlled source and seed

**Decision:** baseline, declarative baseline and mutant declarative runs share the same refinery and seed; the comparator reports structural deltas without assigning a quality score.

**Reason:** otherwise runtime changes can be confused with seed variance, source variance or mere graph growth.

## ADR — Discovery cannot self-promote

**Decision:** Resistant-source discovery may generate a mutation hypothesis but not an accepted operator delta.

**Reason:** Structural recurrence can arise from traversal, runtime, seed, registry or source ambiguity. Treating recurrence as source semantics would convert self-critique into self-confirmation.

**Consequence:** Discovery emits `operator_delta_seed.json` with `gateable=false` and `promotion_forbidden=true`; source review, executable variants, discriminator, before/after and negative tests remain mandatory.

## ADR — Longitudinal recurrence must deduplicate evidence

**Decision:** Identical report/run/signature evidence does not increase recurrence counts.

**Reason:** Re-running the same material must not manufacture stronger evidence merely through repetition.
