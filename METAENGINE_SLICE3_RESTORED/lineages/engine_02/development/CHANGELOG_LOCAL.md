# Local development changelog

## Studio 0.1.0 — 2026-08-11

- добавлен интерактивный launcher;
- добавлен `doctor` с portable SHA-256 fixity check;
- добавлена одно-командная оркестрация полного DOCX-цикла;
- добавлены изолированные run directories и command logs;
- добавлены experiment/operator-delta scaffolds;
- добавлены architecture snapshots;
- добавлены Windows/macOS/Linux launchers;
- добавлены VS Code tasks;
- исходные обязательные portable-assets не изменены.

## Studio 0.2.0 — 2026-08-11

- реализован `RESISTANT-SOURCE / OPERATOR-MUTATION 1.0`;
- добавлен `schemas/operator_delta.schema.json` и AJV hook `validateOperatorDelta`;
- добавлен semantic mutation gate с same-source fixture, rival unitization, GG1, traceability и negative tests;
- реализованы `SUSPEND`, `SPLIT`, `REVISE`, `ADD_CONDITION`;
- добавлены runtime reachability levels `FULL | PARTIAL | NONE`;
- добавлены candidate registry, mutation receipt и rollback target;
- добавлены `delta:gate`, `delta:promote`, `run:living-mutant`;
- mutant registry подключается process-scoped и не переписывает baseline;
- добавлен passing fixture `F-MEDIATION-COMPRESSION → ORIENTATION / SUBSTITUTION`;
- добавлены четыре standalone regression tests mutation engine;
- 29 обязательных portable-assets сохранены неизменными.

## Studio 0.3.0

- Added declarative GX registry and generic generative-gesture interpreter.
- Added declarative living-analysis runtime and CLI.
- Upgraded operator mutation engine so executable generative-gesture splits can reach `FULL`.
- Added passing GX1 split fixture and reproducible gate output.
- Replaced gesture-ID-dependent openness checks with semantic-role checks.
- Added baseline/declarative/mutant-declarative Studio runners.
- Added controlled A/B/C living comparator and structural comparison report.
- Added Studio regression suite covering comparator + gesture runtime + mutation gates.

## Studio 0.4 — Resistant-Source Discovery

- Added structural recurrent-resistance detection grouped by exact source locator.
- Added rival-unitization signatures and conservative mutation-target hypotheses.
- Added deliberately non-promotable `operator_delta_seed` generation.
- Added longitudinal case ledger with evidence deduplication.
- Added `discover:resistance` and `discover:history` Studio commands.
- Made Studio session IDs collision-safe within the same second.
- Added 9 discovery/ledger tests; Studio suite now passes 20/20 in the dependency-light environment.
