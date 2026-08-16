# METAENGINE — СЛЕДУЮЩИЕ КРИТИЧЕСКИ ВАЖНЫЕ ШАГИ

**Дата:** 2026-08-16
**Основание:** Повторный анализ всех отчётов + сравнение с лучшими аналогами
**Отчёты проанализированы:** 24 документа (MASTER_CRITICAL_ANALYSIS, 6 групп A-F, BEST_ANALOGS_COMPARISON, 12 POST_STEP_ANALYSIS, и др.)

---

## 1. СВОДНАЯ ТАБЛИЦА: СРАВНЕНИЕ С ЛУЧШИМИ АНАЛОГАМИ

| # | Категория | MetaEngine | Лучший аналог | Ключевой gap | Сложность | Приоритет |
|---|-----------|------------|--------------|-------------|-----------|-----------|
| 1 | Оркестратор | orchestrator.py (822 LOC монолит) | **LangGraph + Temporal** | Нет durable execution, 34 try/except, нет checkpoint/resume | Hard | **P0** |
| 2 | Fitness оценка | tiered_fitness.py (эвристика L0) | **BoTorch** (Bayesian GP surrogate) | Суррогат — hand-coded формула, не fitted GP; нет acquisition function | Hard | **P0** |
| 3 | Multi-model routing | multi_model_router.py (1 bridge) | **LiteLLM** (100+ providers) | Захардкожен на localhost:3031; нет provider abstraction | Easy | **P0** |
| 4 | Recursive improvement | real_recursive.py (7 rules) | **DSPy** (teleprompter/MIPROv2) | Нет gradient signal; 7 hand-coded heuristics вместо automatic prompt optimization | Medium | P1 |
| 5 | State management | state_bus.py (in-memory) | **Redis** / **NATS** | Нет thread safety; нет durability; нет multi-process support | Medium | P1 |
| 6 | Constitutional AI | constitution.py (12 K0, load-time) | **NeMo Guardrails** (runtime) | Нет runtime rails; invariants — документация, не guardrails | Hard | P1 |
| 7 | Engine diversity | 16 engines (4 native + 12 ref) | **Mixture-of-Experts** (sparse routing) | Reference engines — clean-room simulations, не real executors; round-robin ≠ capability routing | Hard | P1 |
| 8 | Evidence graph | evidence_graph.py (in-memory) | **Neo4j + LlamaIndex** | O(N) lookups; нет indexing; нет vector retrieval; hash brittleness | Medium | P1 |
| 9 | Event publishing | event_publisher.py (JSONL singleton) | **structlog + sse-starlette** | Global singleton; нет schema registry; нет backpressure | Easy | P2 |
| 10 | Dialectical discourse | dialectical_graph.py (10 ops) | **Multi-Agent Debate** (Du 2023) | Operators — template strings, не LLM generations; нет debate rounds | Medium | P2 |

---

## 2. ТОП-5 КРИТИЧЕСКИХ GAP'ОВ

### Gap 1: Orchestrator не durable (P0, 5 недель)
- **Проблема:** 822-LOC монолит, 34 try/except (17 bare pass), crash на barrier 17/30 теряет всё
- **Аналог:** LangGraph (graph definition) + Temporal (durable execution) — industry standard 2026
- **Что делать:** Декомпозировать в LangGraph nodes → добавить Temporal checkpointer → crash recovery

### Gap 2: L0 surrogate не fitted (P0, 2 недели)
- **Проблема:** "Online surrogate" — это hand-coded weighted sum, не trained model. Нет acquisition function.
- **Аналог:** BoTorch (Bayesian Optimization с GP surrogate, q-EI batch acquisition)
- **Что делать:** Wrap BoTorch как L0 surrogate behind ThreeTierFitnessAdapter

### Gap 3: Router захардкожен на 1 bridge (P0, 5 дней)
- **Проблема:** Оба default backend указывают на localhost:3031. Нет provider abstraction.
- **Аналог:** LiteLLM (100+ providers, virtual keys, cost tracking)
- **Что делать:** Заменить internal HTTP calls на LiteLLM Router

### Gap 4: Constitution без runtime enforcement (P1, 4 недели)
- **Проблема:** 12 K0 invariants проверяются только при load. Нет input/output rails.
- **Аналог:** NeMo Guardrails (runtime enforcement, НЕ Anthropic CAI training-time)
- **Что делать:** Добавить ConstitutionRail wrapper вокруг MultiModelRouter.call()

### Gap 5: Evidence graph не масштабируется (P1, 2 недели)
- **Проблема:** In-memory tuple-of-dataclasses. O(N) lookups. Hash-check ломается при любом изменении.
- **Аналог:** Neo4j (durable graph DB) + LlamaIndex (graph-RAG retrieval)
- **Что делать:** Мигрировать на Neo4j backend, добавить vector retrieval

---

## 3. ДОРОЖНАЯ КАРТА (по неделям)

### Неделя 1 — Быстрые победы (≤5 dev-days каждая)

| # | Действие | Усилие | Приоритет |
|---|---------|--------|-----------|
| 1 | **Adopt LiteLLM** в multi_model_router.py | 5 дней | P0 |
| 2 | **Fix state_bus thread safety** (add Lock) | 2 дня | P1 |
| 3 | **Demote EVIDENCE_GRAPH_HASH_MISMATCH** от raise к warning | 1 день | P1 |
| 4 | **Replace event_publisher internals** на structlog + sse-starlette | 1 день | P2 |

### Недели 2-6 — Три P0 архитектурные миграции

| # | Действие | Усилие | Приоритет |
|---|---------|--------|-----------|
| 5 | **BoTorch как L0 surrogate** behind ThreeTierFitnessAdapter | 2 недели | P0 |
| 6 | **Neo4j backend** для evidence_graph.py | 2 недели | P1 |
| 7 | **LangGraph + Temporal** декомпозиция orchestrator | 5 недель | P0 |

### Недели 7-14 — Четыре P1 архитектурные миграции

| # | Действие | Усилие | Приоритет |
|---|---------|--------|-----------|
| 8 | **NeMo runtime rails** на MultiModelRouter.call() | 4 недели | P1 |
| 9 | **DSPy teleprompter** вместо 7 amplify rules | 5 недель | P1 |
| 10 | **Learned top-k engine router** (sparse MoE-style) | 4 недели | P1 |
| 11 | **LLM-ify dialectical_graph** operators | 2 недели | P2 |

### Долгосрочные (опциональные)

| # | Действие | Усилие |
|---|---------|--------|
| 12 | Redis/NATS для state_bus | 2 недели |
| 13 | Promote 2 reference engines to LLM_MODEL | 2 недели |
| 14 | OpenTelemetry tracing | 1 неделя |
| 15 | Multi-Agent Debate в dialectical_graph | 2 недели |

**Всего:** ~31 dev-week (~7.2 dev-months) для полной дорожной карты

---

## 4. 5 МЕСТ, ГДЕ НЕ НАДО СЛЕДОВАТЬ INDUSTRY STANDARD

1. **НЕ применять Anthropic CAI training-time fine-tuning** — нарушает `NO_NORMAL_KERNEL_SELF_MUTATION`
2. **НЕ сокращать 16 engines до 4** — добавить learned top-k router вместо обрезки
3. **НЕ делать K0 invariants learnable** — amendment authority намеренно NOT_IMPLEMENTED
4. **НЕ заменять reference engines на LLM вызовы wholesale** — reference contracts имеют provenance value
5. **НЕ заменять constitution.py целиком** — добавить NeMo rails СВЕРХ, не ВМЕСТО

---

## 5. СЛЕДУЮЩИЙ КРИТИЧЕСКИ ВАЖНЫЙ ШАГ

**Шаг 1: Adopt LiteLLM** (5 дней, P0, Easy)

Это самый высокий leverage за минимальное усилие:
- Заменяет 2 hardcoded backend на 100+ providers
- Добавляет cost tracking, virtual keys, streaming
- Не нарушает constitution (прозрачный routing)
- Включает automatic failover на уровне provider, не только bridge

*End of document.*
