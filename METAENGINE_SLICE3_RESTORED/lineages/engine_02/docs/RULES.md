# Исполнимые правила 0.4

Каждый issue имеет `severity`, стабильный `code`, JSON-path `at` и сообщение. `ERROR` блокирует conformance, `REVIEW` требует решения или даёт `SUSPEND`, `WARNING` сохраняется в отчёте без автоматического повышения статуса.

## TRC, provenance и 4A

| Code/семейство | Условие |
|---|---|
| `CORE_SCHEMA`, `EXTENSION_SCHEMA` | Record не соответствует frozen TRC/module schema |
| `UNKNOWN_RELATION_ID`, `UNKNOWN_EXTENSION` | ID не разрешается через frozen registry |
| `AAG_*`, `O6_RIVALS_REQUIRED`, `O8_POSITIVE_REQUIRED` | Нарушены инварианты или обязательные артефакты операции |
| `ABSENT_BRIDGE_*`, `RT00_ACCEPT`, `LARGE_SCALE_GAP_ACCEPT` | Outcome/promotion сильнее bridge или scale evidence |
| `PROVENANCE_*`, `UNKNOWN_SOURCE_ID`, `LOCAL_SOURCE_HASH_MISMATCH` | Неполный или несогласованный доказательственный след |
| `DAG_*` | Нарушен порядок EM4/KC4/IND4/ID4 либо устойчивость relata |

## 4D

| Code/семейство | Условие |
|---|---|
| `MA4_TOTALIZATION_CONTROLS_REQUIRED` | Сильная реконструкция не содержит хронологии/контрлинии/ограничения масштаба |
| `GE4_DISCRIMINATION_BURDEN_REQUIRED` | Gestell-profile не отличён от локальных технических механизмов |
| `BS4_COUNTERDESCRIPTION_REQUIRED` | Resourceization не проверена независимым counterprofile |
| `TO4_STRONG_FIT_RIVALS_REQUIRED` | Сильный ordering-fit не сравнен с rivals |
| `DAG4D_MA4_RECONSTRUCTION_REQUIRED` | Epochal GE4 заявлен до diachronic MA4 |
| `DAG4D_TO4_DISCRIMINATION_REQUIRED` | Нет конкретной technical-organizational discrimination |
| `DAG4D_BS4_DISCRIMINATION_REQUIRED` | Нет contextual Bestand counterprofile |
| `DAG4D_DIACHRONIC_BRIDGE_REQUIRED` | Machenschaft и Gestell сведены без явного/оспоримого bridge |
| `DAG4D_TOTALIZATION_REVIEW` | Даже корректно упорядоченный totalization остаётся human review |

## Протоколы v3.8

| Code | Условие |
|---|---|
| `UNKNOWN_PROTOCOL`, `PROTOCOL_VERSION_MISMATCH` | Protocol ID/version отсутствует в registry |
| `ARCHIVAL_PROTOCOL_MODE_REQUIRED` | Архивный derivative запущен как действующая норма |
| `PROTOCOL_ANSWER_MISSING`, `UNKNOWN_PROTOCOL_CHECK` | Неполный или посторонний набор ответов |
| `PROTOCOL_EVIDENCE_REQUIRED` | Положительный ответ не имеет evidence ref |
| `HUMAN_JUDGMENT_UNATTESTED` | Интерпретативное `YES` не подписано reviewer/date |
| `PROTOCOL_BLOCKING_FAILURE` | Обязательный check получил blocking `NO` |
| `PROTOCOL_CHECK_UNKNOWN`, `PROTOCOL_SUSPENDED` | Недостающий доступ/данные/решение переводят run в `SUSPEND` |
| `PROTOCOL_OUTCOME_MISMATCH` | Заявленный исход расходится с вычисленным |

## Research, agreement и аргументация

| Code | Условие |
|---|---|
| `RESEARCH_GATE_BLOCKED` | Замороженный план нельзя исполнять из-за DATA/AUTH/LIC/CODER |
| `PREREGISTRATION_DEVIATION`, `PLAN_ID_MISMATCH` | Текущий план отличается от snapshot или lock относится к другому плану |
| `CODER_NOT_INDEPENDENT`, `UNKNOWN_CODER_IN_ANNOTATIONS` | Reliability загрязнена зависимым/неизвестным кодировщиком |
| `AGREEMENT_THRESHOLD_FAILED` | α/CI/multilabel metric ниже frozen threshold |
| `RARE_CODE_UNDERPOWERED` | Код имеет меньше 20 double-coded units |
| `ARGUMENT_*`, `ISSUE_CLAIM_UNKNOWN` | Граф содержит неразрешённые claims/schemes либо неверный declared status |
| `CRITICAL_QUESTION_MISSING` | Обязательный вопрос схемы отсутствует |
| `CRITICAL_QUESTION_OPEN`, `CRITICAL_QUESTION_EVIDENCE_MISSING` | Аргумент приостановлен открытым/необоснованным CQ |

## Semantic review rules

`RT21_LEXICAL_MISMATCH`, `RT17_LEXICAL_MISMATCH`, `RT06_CAUSAL_EVIDENCE_WEAK`, `RT07_GROUNDING_RATIONALE_WEAK`, `NODE_KIND_CLAIM_SUSPECT`, `BRIDGE_REVIEW_REQUIRED` и domain-specific totalization flags являются эвристиками. Они не выбирают заменяющий RT и не исправляют запись без решения эксперта.

## Corpus Refinery

| Правило | Условие |
|---|---|
| `REFINERY_ARTIFACT_MISMATCH` | DOCX hash не совпадает с hash существующего page-run |
| `REFINERY_SOURCE_MISMATCH` | intake и source manifest указывают разные source IDs |
| `REFINERY_PAGE_RUN_POLICY` | импортируемый bundle содержит expressive/raw text |
| `CORPUS_REFINERY_SCHEMA_FAILED` | хотя бы один segmentation/source/ledger/hypothesis/archive/formula artifact не проходит схему |
| `UNRESOLVED` fallback | top score слаб, margin недостаточен или кандидаты связаны |
| Archive without deletion | exact duplicate и tool/log сохраняют selector/hash; near duplicate только связывается для review |
| Claim non-promotion | A/P/B и strongest rival остаются `null`; layer и RT — candidates, не gold |

## Autonomous Expert Cycle

| Правило/ошибка | Условие |
|---|---|
| `EXPERT_REFINERY_SCHEMA_FAILED` | evidence layer не проходит одну из обязательных refinery schemas |
| `EXPERT_SOURCE_ID_MISMATCH` / `EXPERT_ARTIFACT_HASH_MISMATCH` | связанные артефакты относятся к разным источникам или DOCX hashes |
| `EXPERT_PROFILE_SCHEMA_FAILED` | профиль не задаёт terminal policy, A/P/B, burden, scale, rivals или global synthesis |
| Evidence threshold gate | topic/matrix, число кандидатов или число различимых групп ниже профиля → `INSUFFICIENT` |
| Source-dependent gate | claim-level citations ниже минимума → `INSUFFICIENT`; упоминания GA и псевдолокаторы не засчитываются |
| Universalization gate | общий словарь/выборка без domain/source burden → `REJECTED` для заявленной промоции |
| Internal-model ceiling | внутрикорпусная реконструкция не может получить `SUPPORTED` без внешнего evidence; максимум `QUALIFIED` |
| Test-design scope lock | `SUPPORTED` относится только к пригодности стресс-теста, не к истинности проверяемой теории |
| `EXTERNAL_SOURCE_TRANSFER_BLOCKED` | модельный backend запрошен без явного разрешения переноса исходных фрагментов |
| `EXPERT_DOCX_HASH_MISMATCH` | модельный backend получил DOCX, не совпадающий с refinery fixity |
| `OPENAI_ASSESSMENT_SCHEMA_FAILED` | модельный проход не соответствует strict structured contract |
| `OPENAI_ASSESSMENT_SELECTOR_FABRICATION` | модель вернула selector вне детерминированного evidence set; проход откатывается к profile result |
| Verbatim guard | восьмитокенное совпадение с исходным фрагментом запрещает сохранение модельного прохода и вызывает deterministic fallback |
| Terminal completeness | каждый thesis обязан завершиться `SUPPORTED`, `QUALIFIED`, `REJECTED` или `INSUFFICIENT` |

`INSUFFICIENT` — не незавершённый `SUSPEND`, а финальный ответ текущего expert run: данных недостаточно, чтобы предпочесть тезис сильнейшему доступному сопернику. Это решение может измениться только в новом прогоне с изменённым evidence/profile и новой provenance.

## Frozen empirical benchmark

| Правило/ошибка | Условие |
|---|---|
| `BENCHMARK_*_SCHEMA` | manifest, predictions, packet, annotation, gold или result нарушает versioned JSON contract |
| `BENCHMARK_MANIFEST_FIXITY_FAILED` / `BENCHMARK_FILE_FIXITY_FAILED` | frozen manifest либо sealed predictions изменены после lock |
| `BLIND_PACKET_FIXITY_FAILED` | coder packet изменён после freeze |
| `BENCHMARK_ID_MISMATCH` / `*_BENCHMARK_MISMATCH` | артефакт labels/gold относится к другому benchmark |
| `PREDICTION_UNIT_SET_MISMATCH` / `BENCHMARK_UNIT_SET_MISMATCH` | система, coder или gold не покрывает ровно frozen unit set |
| `DUPLICATE_INDEPENDENT_CODER` | две raw-разметки имеют один coder id |
| `ANNOTATION_PACKET_MISMATCH` | raw labels не связаны с одним из frozen blind packets |
| `GOLD_ANNOTATION_FIXITY_MISMATCH` | gold не перечисляет точные byte SHA-256 всех используемых raw annotations |
| `INDEPENDENT_LABELS_REQUIRED` / `ADJUDICATED_GOLD_REQUIRED` | performance evaluation блокируется без двух coders и gold |
| `BENCHMARK_UNDERPOWERED` | меньше 80 units либо меньше 20 gold units хотя бы одного класса |
| `BENCHMARK_RELIABILITY_FAILED` | pre-adjudication α или нижняя граница CI ниже frozen threshold |
| `BENCHMARK_PROMOTION_FAILED` | провален F1/CI, baseline improvement, dangerous-overpromotion либо calibration gate |

`PASS_PROMOTION_GATE` относится только к frozen sample. Synthetic fixture проверяет исполнение формул и gates, но не является независимой эмпирической валидацией.

## Вычисление исхода

1. Любой `ERROR` → `FAIL`.
2. Неразрешённый обязательный доступ/шлюз → `SUSPEND`.
3. Нет ошибок, но есть содержательное `REVIEW` → `PASS + HUMAN REVIEW`.
4. Нет ошибок и review → `PASS`.

Во всех случаях `PASS` означает соответствие реализованному контракту, а не истинность анализа.

Для expert cycle вычисляется отдельный исход:

1. Не выполнен структурный intake → run не создаётся.
2. Выполнен thesis burden в заявленном масштабе → `SUPPORTED`.
3. Сохраняется ограниченное ядро, но блокируется усиление → `QUALIFIED`.
4. Соперник или запрещённый переход решающи → `REJECTED`.
5. Данных недостаточно для выбора → `INSUFFICIENT`.
6. После терминализации всех тезисов SYNTHESIS всегда выпускает `FINAL_ANALYTICS`; его claim ceiling остаётся run-bound.
