# Дорожная карта автоматизации

## 0.1 — Conformance kernel — выполнено

- structural validation TRC-0.3 и 4A;
- referential integrity RT00–RT28 и AAG invariants;
- provenance/source catalog и semantic lint;
- 4A execution DAG, repaired fixtures, mutation suite и CLI.

## 0.2 — Protocol and research engine — выполнено

- полный heading-level инвентарь v3.8: 123 вхождения → 40 семейств;
- versioned protocol runner с evidence refs, attestation и `PASS/REVIEW/SUSPEND/FAIL`;
- изоляция архивных процедур через `ARCHIVAL_REVIEW`;
- реконструированные MA4/GE4/BS4/TO4 и блокирующий 4D DAG;
- локальная заморозка research plan, canonical SHA-256 и path-level deviations;
- nominal Krippendorff α, bootstrap CI и multilabel agreement;
- AIF/Carneades-inspired argument graph и critical questions;
- TXT/Markdown analyzer, который создаёт только review-candidates;
- attached RO-Crate 1.3 и release manifest с SHA-256;
- сквозная suite положительных, отрицательных и mutation tests.

Promotion gate 0.2: все детерминированные компоненты должны проходить тесты; любое содержательное повышение остаётся на human/domain review. Этот gate выполнен для developer release, но не является внешней валидацией.

## 0.2.2 — Page-aware single-work pilot — выполнено

- schema source manifest: bibliography, PDF/text fixity, pagination, access class и edition crosswalk;
- `analyze-pages` с TEI-page milestones и W3C Web Annotation-inspired position selectors;
- `REFERENCE_ONLY`/`DERIVATIVE_ONLY` gates и transient acquisition без full-text redistribution;
- German modal ambiguity: bare `muss/soll` → RT00 с rivals RT04/RT21;
- discourse-feature и term indexes с отдельным lexical claim ceiling;
- полный пилот первой работы GA 1: 11 страниц, 280 units, 24 review candidates;
- pro/con argument graph, source/claim/ontology/data/ablation protocol runs;
- legacy/page/notes/modal ablation и обязательные mutation tests.

Promotion gate 0.2.2: безопасная локализация и проверяемость источника достигнуты для одной работы. Semantic accuracy, edition-complete crosswalk и external comparator не установлены.

## 0.2.3 — DOCX и кириллический стресс-тест — выполнено

- `analyze-docx` с DOCX job, ZIP/OOXML audit и source admission;
- изолированный LibreOffice render и transient `pdftotext` без выпуска полного текста;
- `RENDERER_DERIVED` как отдельный авторитет пагинации;
- аудит metadata, headings, formulas/short fragments, exact duplicates, citations и interaction residue;
- Unicode-aware boundaries для DE/RU/EN lexical rules;
- полный прогон 697-страничного русскоязычного досье: 13 242 units, 840 candidates;
- отрицательная абляция 6 → 840 candidates и запрет выдавать восстановленный recall за precision;
- quarantine policy для composite hypothesis corpus, не являющегося independent source.

Promotion gate 0.2.3: форматный intake и кириллическая маршрутизация работают, но semantic accuracy, near-duplicate consolidation и source-resolved claim graph не установлены.

## 0.2.4 — Corpus Refinery — выполнено

- `refine-docx` с переиспользованием fixity-checked page run или свежим transient render;
- три competing unitizations: OOXML paragraphs, renderer units и bounded argument windows;
- review-only маршрутизация `SOURCE`, `RECONSTRUCTION`, `PROJECT_CLAIM`, `RIVAL_OBJECTION`, `PROTOCOL_TOOL_LOG`, `UNRESOLVED`;
- source map с catalog aliases, GA-volume locators и hashed unresolved pseudo-citations;
- claim ledger JSONL: selector, origin, type, scale, RT candidates, пустые A/P/B, revision condition и decision history;
- lexical hypothesis bank и семичленная heterogeneous case matrix;
- exact/minhash near-duplicate audit, representative links и archive-without-deletion;
- отдельный OMML registry: 1 139 containers / 3 908 math runs без текста формул;
- полный прогон досье: 33 870 OOXML segments, 10 569 argument units, 2 387 ledger entries, 0 schema errors;
- privacy audit: 1 210 длинных исходных paragraphs проверены, verbatim leaks = 0.

Promotion gate 0.2.4: corpus preservation, selectors и review routing воспроизводимы. Source resolution, A/P/B, strongest rivals, semantic precision/recall и canonical argument остаются `SUSPEND` до независимой разметки.

## 0.3 — Autonomous Expert Cycle — выполнено

- `expert-cycle`: готовый refinery evidence layer → терминальный экспертный анализ;
- `expert-docx`: одна команда для DOCX → Corpus Refinery → expert cycle → `FINAL_ANALYTICS.md/.json`;
- автоматический профиль для нового корпуса из thematic hypotheses, source burden и heterogeneous matrices;
- предметный профиль Хайдеггера с 9 явными тезисами, A/P/B, scale, burden, RT и strongest rival;
- четыре последовательных прохода: RECONSTRUCTOR, CRITIC, ADJUDICATOR, SYNTHESIS;
- четыре обязательных финальных статуса: `SUPPORTED`, `QUALIFIED`, `REJECTED`, `INSUFFICIENT`;
- детерминированные ceilings имеют приоритет над модельным решением; `INSUFFICIENT` завершает прогон без симуляции evidence;
- необязательный OpenAI Responses adapter: strict JSON Schema, explicit source-transfer authorization, selector admission и verbatim guard;
- текущий GA-досье прогон: 9/9 terminal, 2 supported, 4 qualified, 1 rejected, 2 insufficient;
- `FINAL_ANALYTICS` содержит итоговый вердикт, A/P/B, доказательную базу, strongest rival, decisive reasons, limitations и next actions;
- suite расширена до 42 тестов, включая end-to-end, transfer block и попытку модельного обхода claim ceiling.

Promotion gate 0.3: полный цикл технически завершает каждый тезис и выпускает финальную аналитику; модель не может обойти source/burden/scale gates. Финальность является run-bound adjudication, а не external semantic validation.

## 0.4 — Empirical validation infrastructure — реализована; внешнее исследование заблокировано

- `benchmark-init` замораживает один или несколько expert cycles, codebook, thresholds, manifest SHA-256 и два blind packets;
- system predictions и fixed baselines отделены в sealed artifact и не передаются кодировщикам;
- annotation/gold schemas требуют blindness, source access, independence, evidence refs и byte-hash lineage;
- `benchmark-evaluate` блокируется без двух raw annotations и adjudicated gold;
- agreement/CI считаются до adjudication; затем доступны confusion matrix, precision/recall/F1, bootstrap CI, abstention/coverage, Brier/ECE, risk–coverage и dangerous overpromotion;
- frozen gate требует 80 units, 20 gold items на класс и превосходства над strongest preselected fixed baseline;
- prediction/source fixity mutations, pending-label и 80-unit synthetic PASS покрыты regression tests; suite расширена до 48 тестов;
- реальный 9-unit GA benchmark создан и корректно имеет `BLOCKED_PENDING_INDEPENDENT_LABELS` + underpowered warning.

Внешне остаются обязательными: лицензированный immutable multi-document corpus snapshot; два независимых предметных кодировщика; pilot и при необходимости новая версия codebook; сильный domain-native comparator; masking/removal/protocol-ablation; публичная registration с доверенным timestamp; independent review 4A/4D/translation bridges.

Promotion gate 0.4: инфраструктура реализована, но сам gate ещё не пройден на реальных данных. Движок должен либо воспроизводимо превзойти baseline и сильного внешнего конкурента, либо быть сокращён до контролей, выдержавших абляцию.

## 0.5 — Review workspace

- локальный web-интерфейс side-by-side: source spans, rival candidates, registry definitions и bridge burden;
- accept/qualify/block/merge/reject без автоматического `GOLD`;
- неизменяемая история revisions, defeats, deviations и adjudication;
- экспорт TRC bundle, protocol bundle и research report.

## Gate версии 1.0

Версия 1.0 допустима только после:

1. устойчивого heterogeneous-corpus ingestion;
2. независимого coder pilot и внешнего semantic/domain review;
3. зарегистрированного списка failure modes и отрицательных результатов;
4. доказательства пользы относительно baseline и сильных конкурентов;
5. сохранения Domain Deference, claim ceilings и права `SUSPEND`;
6. повторяемой сборки с проверяемыми provenance и fixity.
