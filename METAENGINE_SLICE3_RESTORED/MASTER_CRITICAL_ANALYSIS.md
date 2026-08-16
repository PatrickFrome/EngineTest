# METAENGINE — МАСТЕР-ОТЧЁТ КРИТИЧЕСКОГО АНАЛИЗА ВСЕХ МОДУЛЕЙ

**Task ID:** 109-master-critical-analysis
**Date:** 2026-08-15
**Scope:** Последовательный критический анализ каждого модуля и каждого механизма всего проекта MetaEngine (102 модуля, 24,740 LOC)

---

## 1. СВОДНАЯ СТАТИСТИКА

| Группа | Модулей | LOC | Тестов | Impl | Tests | Conn | Overall |
|--------|---------|-----|--------|------|-------|------|---------|
| A: Core Engine | 17 | 3,200 | 582 | 5.5 | 2.4 | 5.7 | 6.0 |
| B: Training | 12 | 4,944 | 3,911 | 6.5 | 6.1 | 5.2 | 6.2 |
| C: Fitness | 8 | 3,594 | 1,928 | 6.8 | 6.5 | 5.5 | 6.6 |
| D: Infrastructure | 12 | 3,008 | 1,551 | 6.8 | 4.9 | 4.4 | 6.0 |
| E: Analysis | 16 | 4,071 | 1,344 | 6.2 | 2.9 | 3.3 | 5.2 |
| F: Architecture | 16 | 3,227 | 720 | 6.8 | 2.3 | 5.3 | 5.5 |
| **ИТОГО** | **81** | **22,044** | **10,036** | **6.4** | **3.7** | **4.7** | **5.9** |

**Оставшиеся 21 модуль** — мелкие utility/disconnected (fusion, effects, coalitions, etc.)

---

## 2. TOP 10 КРИТИЧЕСКИХ НАХОДОК (cross-cutting)

### 1. orchestrator.py — антипаттерн монолит (810 LOC, 34 try/except, 17 с bare pass)
Один метод `run()` содержит 700 строк, 63 импорта, 34 блока `try/except Exception`, из которых 17 с `pass`. Использование `if 'actual_q' in dir()` для проверки локальных переменных. Integration тесты проверяют наличие строк в исходном коде, а не поведение.

### 2. 58 из 102 модулей (57%) не имеют тестов
Включая критические: orchestrator.py, dialectical_graph.py, event_publisher.py, frontier_control_plane.py (598 LOC), core4_reentry.py (292 LOC). Test coverage average = 3.7/10.

### 3. _call_llm + health_check дублируется в 4 модулях
rlaif_trainer, redteam_adversary, llm_judge, unified_benchmark — ~150 LOC копирования. Любое изменение bridge протокола требует редактирования 4 файлов.

### 4. 31 модуль DISCONNECTED (не используется orchestrator или real_recursive)
Включая: strict_test_factory (739 LOC), architecture_sources (706 LOC), api_server (674 LOC), unified_benchmark (633 LOC), external_validator (553 LOC), cross_run_accumulator (369 LOC), recursive_loop (347 LOC), core4_reentry (292 LOC), polycentric_reentry (281 LOC).

### 5. fusion.py — 23 LOC заглушка, не делает fusion
Назван "fusion", но возвращает passthrough inventory dict. Строка "FUSION_WITHOUT_ERASURE" — это ярлык, не алгоритм.

### 6. real_fitness.py игнорирует theta
Строки 348-359 хардкодят `max_rounds=1, max_deep_engines=2` в experiment_policy, переопределяя theta-derived ArchitecturePolicy. Две из четырёх размерностей theta не имеют эффекта на fitness.

### 7. strict_test_factory.py — SKIP-as-PASS bug
8 из 25 тест-кейсов возвращают `True` (PASS) когда файлы данных отсутствуют. Счётчик `skipped` всегда 0. Это раздувает pass-rate.

### 8. task_conditional_selector.py — effectively no-op
Rules проверяют `"MODEL_PLUS_VERIFIER"` / `"SINGLE_MODEL"` / `"FEDERATION"`, но OrganizationType enum содержит `RESOURCE_PLUS_VERIFIER` / `ONE_RESOURCE` / `HIERARCHICAL_FEDERATION`. Ни одно правило не срабатывает. "Online adaptation" claim — ложный.

### 9. Cross-run learning loop OPEN для большинства модулей
Только AutonomousExperimentLoop сохраняет состояние. TaskConditionalSelector, ArchitectureSearchGenerator, CurriculumGenerator, ArchitectureSynthesizer, GenerationComparator — все создаются PER RUN с seed=42. Детерминированно, но не учатся.

### 10. ~80 magic constants без центрального config
12 weight dicts, thresholds, hardcoded paths разбросаны по 20+ модулям. Нет `training_config.py` или `metaengine_config.py`.

---

## 3. TOP 10 РЕКОМЕНДАЦИЙ (по приоритету)

### P0 (Critical — must fix)

| # | Рекомендация | Effort | Impact |
|---|-------------|--------|--------|
| 1 | **Декомпозировать orchestrator.run() в 7 phase классов** | ~16h | Устраняет 810-LOC монолит, 34 try/except, делает код тестируемым |
| 2 | **Написать 11 критических test файлов** (orchestrator, dialectical_graph, event_publisher, frontier_control_plane, core4_reentry, native_reentry_compiler, worldbench, biographies, local_outcome_oracle, telemetry, meta_learning) | ~30h | Поднимает test coverage с 3.7 до ~6.0 |
| 3 | **Исправить real_fitness.py theta override** — удалить хардкод `max_rounds/max_deep_engines` | ~2h | Восстанавливает 2 из 4 размерностей theta |

### P1 (Important — should fix)

| # | Рекомендация | Effort | Impact |
|---|-------------|--------|--------|
| 4 | **Извлечь `llm_bridge_client.py`** — убрать дублирование _call_llm из 4 модулей | ~2h | -150 LOC дублирования, 1-file edit для bridge changes |
| 5 | **Исправить strict_test_factory SKIP-as-PASS** — return None вместо True, считать skips | ~3h | Восстанавливает достоверность pass-rate |
| 6 | **Исправить task_conditional_selector policy-name mismatch** — синхронизировать rule strings с enum values | ~1h | Активирует "online adaptation" |
| 7 | **Wire cross_run_accumulator в orchestrator** — закрыть cross-run learning loop | ~4h | Накопление состояния между запусками |

### P2 (Nice to have)

| # | Рекомендация | Effort | Impact |
|---|-------------|--------|--------|
| 8 | **Удалить или wire up 745 LOC dead code** (PolycentricReentry, Core4Reentry, organization_legacy) | ~3h | -745 LOC, чище кодовая база |
| 9 | **Извлечь magic constants в central config** — `training_config.py`, `scheduler_config.py` | ~8h | Убирает ~80 хардкодов |
| 10 | **Заменить fusion.py заглушку на real fusion algorithm ИЛИ переименовать в inventory.py** | ~4h | Устраняет misleading naming |

---

## 4. ЯРКИЕ ПРИМЕРЫ (Bright Spots)

| Модуль | Оценка | Почему |
|--------|--------|--------|
| constitution.py | 9/10 | Frozen dataclasses, fail-closed amendment authority, path-traversal protection |
| architecture_policy.py | 9/10 | Atomic CAS promotion, I1 backward-compat hash fallback, MUTABLE/FORBIDDEN_FIELDS |
| mechanism_library.py | 9/10 | Full A0-A3 state machine, evidence-gated admission, hash re-verification |
| amplify_distill.py | 8/10 | ML rule weights, persistence, 7 amplify rules with bounded updates |
| multi_model_router.py | 8/10 | Cost-aware routing, failover, background reaper, UCB exploration |
| signed_provenance.py | 9/10 | Ed25519 signing, cross-run verification |
| autonomous_loop.py | 7/10 | ONLY module with proper cross-run persistence |

---

## 5. ЗАМЕНА АЛЬТЕРНАТИВ (Greenfield Strategy)

Если бы проект строился с нуля:

| Текущий модуль | Замена | Причина |
|----------------|--------|---------|
| tiered_fitness.py surrogate | botorch (Bayesian Optimization) | GP surrogate с uncertainty estimates |
| real_recursive.py flywheel | ray.tune.PopulationBasedTraining | Battle-tested PBT implementation |
| multi_model_router.py | litellm.Router | Unified API for 100+ providers |
| state_bus.py | redis / nats | Thread-safe, persistent pub/sub |
| event_publisher.py | sse-starlette + structlog | Standard SSE + structured logging |
| _call_llm duplication | httpx + tenacity | Async HTTP client with retry |
| fusion.py | Real fusion algorithm (e.g., ensemble voting) | Current is a stub |

**Потенциальная экономия**: 3,594 LOC → ~800 LOC glue code (Group C alone)

---

## 6. ОЦЕНКА СВЯЗНОСТИ

| Метрика | Значение |
|---------|----------|
| Модулей используются orchestrator | 63/102 (62%) |
| Модулей используются real_recursive | 17/102 (17%) |
| DISCONNECTED модулей | 31/102 (30%) |
| Hub модули (>10 importers) | util.py (91), constitution.py (12), architecture_policy.py (10) |
| Leaf модули (0 importers) | 31 modules |

---

## 7. ОЦЕНКА ПОКАЗАТЕЛЕЙ ПО ГРУППАМ

```
                    Impl Quality    Test Coverage    Connectivity
Group A (Core):     ████████░░ 5.5  ███░░░░░░░ 2.4   ████████░░ 5.7
Group B (Training): █████████░ 6.5  ███████░░░ 6.1   ███████░░░ 5.2
Group C (Fitness):  █████████░ 6.8  ████████░░ 6.5   ███████░░░ 5.5
Group D (Infra):    █████████░ 6.8  ██████░░░░ 4.9   ██████░░░░ 4.4
Group E (Analysis): ████████░░ 6.2  ███░░░░░░░ 2.9   ████░░░░░░ 3.3
Group F (Arch):     █████████░ 6.8  ██░░░░░░░░ 2.3   ██████░░░░ 5.3
```

**Вывод**: Implementation quality приемлемая (6.4/10), но test coverage критически низкая (3.7/10). Groups E и F — наименее покрытые (2.9 и 2.3). Group B — лучшая (6.1, потому что trainers хорошо протестированы).

---

## 8. ИТОГОВЫЙ ВЕРДИКТ

MetaEngine — это **коллекция из 102 модулей (24,740 LOC) с приемлемой implementation quality (6.4/10), но критически низкой test coverage (3.7/10)**. 31 модуль (30%) полностью disconnected. Orchestrator — монолит с 34 try/except блоками. Cross-run learning loop открыт только для 1 из 6 "learning" модулей. ~80 magic constants без центрального config.

**Constitution compliance**: отличная — все модули с `truth_effect=NONE`, нет truth promotion.

**Приоритет**: декомпозиция orchestrator + написание 11 критических test файлов + исправление real_fitness theta override.

---

*End of master report.*
