# METAENGINE — Критический анализ модулей 64-69 + программа улучшений

**Task ID:** 95  
**Дата:** 2026-08-15

---

## ЧАСТЬ 1. ИНВЕНТАРИЗАЦИЯ МОДУЛЕЙ (64-69)

| Фаза | Модуль | LOC | Тесты | Назначение |
|------|--------|-----|-------|-----------|
| 64 | `api_server.py` | 442 | 24 | REST API (11 endpoints, port 8080) |
| 67 | `tiered_fitness.py` | 347 | 26 | 3-tier fitness (L0+L1+L2 real LLM) |
| 67 | `pbt_fitness_wiring.py` | 118 | 18 | PBT/ES ↔ tiered adapter bridge |
| 68 | `real_recursive.py` | 276 | 19 | Real recursive improvement flywheel |
| 69 | `multi_model_router.py` | 357 | 30 | Multi-model routing + failover |
| **Total** | **5 модулей** | **1540** | **117** | |

---

## ЧАСТЬ 2. АНАЛИЗ СВЯЗНОСТИ

### 2.1 Текущая связность

```
api_server.py ──────────────→ (NONE — doesn't import tiered/recursive/router)
tiered_fitness.py ──────────→ (NONE — standalone, hardcoded bridge URL)
pbt_fitness_wiring.py ─────→ tiered_fitness (imports ThreeTierFitnessAdapter)
real_recursive.py ──────────→ tiered_fitness + pbt_fitness_wiring + amplify_distill + pbt_trainer
multi_model_router.py ──────→ (NONE — standalone, not connected to tiered_fitness)
```

### 2.2 КРИТИЧЕСКИЕ GAP'ы связности

**GAP #1: multi_model_router НЕ подключён к tiered_fitness**
- `ThreeTierFitnessAdapter._evaluate_l2()` делает прямой `urllib.request.urlopen("http://localhost:3031/...")` — НЕ через `MultiModelRouter`
- Router существует, но не используется!
- **Impact:** failover не работает при rate-limit в L2 evaluation

**GAP #2: real_recursive НЕ использует multi_model_router**
- `RealRecursiveRunner` создаёт `ThreeTierFitnessAdapter` напрямую
- Нет round-robin между моделями
- **Impact:** все L2 calls идут на одну модель (glm-1), нет диверсификации

**GAP #3: api_server НЕ экспонирует tiered_fitness / real_recursive**
- API имеет `/api/benchmark` но нет `/api/fitness`, `/api/recursive`
- Нельзя запустить real recursive improvement через API
- **Impact:** dashboard не показывает real-time fitness/recursion

**GAP #4: orchestrator.run() НЕ вызывает новые модули**
- Phase 48 wired trace_extractor + faithfulness + RLAIF
- Но tiered_fitness, real_recursive, multi_model_router — НЕ wired
- **Impact:** orchestrator runs не benefit от 3-tier fitness

---

## ЧАСТЬ 3. СЛАБЫЕ МЕСТА (по модулю)

### 3.1 api_server.py — 5 слабых мест

| # | Слабое место | Severity | Описание |
|---|-------------|----------|---------|
| W1 | Нет auth | CRITICAL | API доступна без аутентификации — кто угодно может запустить benchmark |
| W2 | Нет rate limiting на API | MAJOR | `POST /api/benchmark/run` может спамить LLM bridge |
| W3 | Нет WebSocket | MAJOR | Real-time monitoring невозможен (только polling) |
| W4 | Hardcoded root path | MINOR | `root: Path = Path(".")` — не работает из других директорий |
| W5 | Не экспонирует fitness/recursive | MAJOR | Dashboard не видит real-time fitness data |

### 3.2 tiered_fitness.py — 6 слабых мест

| # | Слабое место | Severity | Описание |
|---|-------------|----------|---------|
| W6 | Hardcoded LLM question | CRITICAL | L2 всегда спрашивает "What is 17 * 23?" — fitness не оценивает реальные задачи |
| W7 | Hardcoded model name | MAJOR | `"model": "metaengine-glm-1"` — не использует MultiModelRouter |
| W8 | Hardcoded bridge URL | MAJOR | `"http://localhost:3031/..."` — нет конфигурации |
| W9 | L2 оценивает только correctness+disclaimer | MINOR | Не проверяет reasoning quality, completeness, constitution |
| W10 | Не подключён к orchestrator | MAJOR | Orchestrator runs не benefit от tiered fitness |
| W11 | L0 heuristic неадаптивный | MINOR | Fixed formula — не учится из L2 результатов (surrogate не обновляется) |

### 3.3 pbt_fitness_wiring.py — 2 слабых места

| # | Слабое место | Severity | Описание |
|---|-------------|----------|---------|
| W12 | Не передаёт temperature из policy | MAJOR | `temperature: 0.4` hardcoded — не извлекается из ArchitecturePolicy |
| W13 | Не публикует в state bus | MINOR | Fitness results не публикуются в TrainingStateBus |

### 3.4 real_recursive.py — 5 слабых мест

| # | Слабое место | Severity | Описание |
|---|-------------|----------|---------|
| W14 | Hardcoded metrics для amplification | CRITICAL | `marl_foe_mean: 0.02`, `faithfulness_mean: 0.61` — фиксированные значения вместо реальных |
| W15 | Не использует MultiModelRouter | MAJOR | Все L2 calls через hardcoded bridge |
| W16 | Amplify использует только 7 правил | MINOR | Нет ML-based amplification (learning what works) |
| W17 | Не загружает накопленные metrics | MAJOR | Не читает accumulated_state.json для предыдущих metrics |
| W18 | Distillation не persist insights | MINOR | Insights не сохраняются между runs |

### 3.5 multi_model_router.py — 4 слабых места

| # | Слабое место | Severity | Описание |
|---|-------------|----------|---------|
| W19 | Не подключён к tiered_fitness | CRITICAL | Router существует, но не используется! |
| W20 | Оба бэкенда на одном bridge | MAJOR | `localhost:3031` для обоих — нет реальной изоляции |
| W21 | Нет health recovery в фоне | MINOR | COOLDOWN проверяется только при следующем call, нет background reaper |
| W22 | Не настраивает failover strategy | MINOR | Нет cost-aware routing (предпочитать дешёвые модели) |

---

## ЧАСТЬ 4. ПРОГРАММА КРИТИЧЕСКИХ УЛУЧШЕНИЙ

### Приоритет P0 — КРИТИЧНО (must fix before production)

| # | Улучшение | Модуль | Описание | Effort |
|---|----------|--------|---------|--------|
| **C1** | **Wire MultiModelRouter → TieredFitness** | tiered_fitness | Заменить hardcoded `urllib.request.urlopen` на `MultiModelRouter.call()` | Small |
| **C2** | **Replace hardcoded L2 question** | tiered_fitness | L2 должен оценивать по набору задач (math, logic, reasoning), не один "17*23" | Medium |
| **C3** | **Replace hardcoded metrics** | real_recursive | Загружать реальные metrics из accumulated_state.json, не хардкодить | Medium |
| **C4** | **Add API auth** | api_server | Token-based auth (Bearer header) для POST endpoints | Small |
| **C5** | **Wire orchestrator → tiered fitness** | orchestrator | Post-run: evaluate engine_16 via tiered fitness, publish to bus | Medium |

### Приоритет P1 — ВАЖНО (should fix for quality)

| # | Улучшение | Модуль | Описание | Effort |
|---|----------|--------|---------|--------|
| **I1** | **Extract temperature from policy** | pbt_fitness_wiring | Читать `temperature` из ArchitecturePolicy (добавить поле) | Small |
| **I2** | **API endpoints for fitness/recursive** | api_server | `GET /api/fitness`, `GET /api/recursive`, `POST /api/recursive/run` | Medium |
| **I3** | **Publish fitness to state bus** | pbt_fitness_wiring | После evaluate — публиковать reward в TrainingStateBus | Small |
| **I4** | **Load accumulated metrics** | real_recursive | Читать previous generation metrics из storage/accumulated_state.json | Small |
| **I5** | **L0 surrogate learns from L2** | tiered_fitness | Когда L2 оценивает, обновлять L0 heuristic weights (surrogate adaptation) | Large |
| **I6** | **API rate limiting** | api_server | Max 1 benchmark run per 60s, queue mechanism | Small |

### Приоритет P2 — УЛУЧШЕНИЕ (nice to have)

| # | Улучшение | Модуль | Описание | Effort |
|---|----------|--------|---------|--------|
| **N1** | WebSocket real-time | api_server | Push fitness/recursion progress via WebSocket | Large |
| **N2** | Background health recovery | multi_model_router | Timer-based reaper to check unhealthy backends | Small |
| **N3** | Cost-aware routing | multi_model_router | Prefer cheaper models for simple tasks | Medium |
| **N4** | Distillation persistence | real_recursive | Save distillation insights across runs | Small |
| **N5** | ML-based amplification | real_recursive | Learn which amplify rules work best (instead of fixed 7 rules) | Large |

---

## ЧАСТЬ 5. СВЯЗНОСТЬ — ИДЕАЛЬНАЯ АРХИТЕКТУРА

```
API Server (port 8080)
    ├── GET /api/fitness → tiered_fitness summary
    ├── POST /api/recursive/run → real_recursive runner
    └── GET /api/recursive → recursive results

Orchestrator.run()
    └── POST-RUN: tiered_fitness.evaluate(engine_16) → publish to state_bus

RealRecursiveRunner
    ├── ThreeTierFitnessAdapter
    │     ├── L0: heuristic (surrogate)
    │     ├── L1: constitution check
    │     └── L2: MultiModelRouter.call() ← (C1 fix)
    │              ├── Backend 1 (glm-1)
    │              └── Backend 2 (glm-thinking)
    ├── AmplifyDistillCycle
    │     └── loads real metrics from accumulated_state ← (C3 fix)
    └── PBT with tiered fitness
          └── publishes to TrainingStateBus ← (I3 fix)
```

---

## ЧАСТЬ 6. ИТОГ

### Статистика

- **5 модулей, 1540 LOC, 117 тестов**
- **17 слабых мест** выявлено (5 CRITICAL, 7 MAJOR, 5 MINOR)
- **5 критических улучшений (P0)** + 6 важных (P1) + 5 nice-to-have (P2)
- **4 критических gap'а связности**: router↔tiered, tiered↔orchestrator, api↔fitness, recursive↔accumulated

### Главный вывод

Модули 64-69 **работают индивидуально** (117 тестов pass), но **не интегрированы друг с другом**:
- MultiModelRouter не подключён к TieredFitness (критичнейший gap)
- RealRecursive использует hardcoded metrics вместо реальных
- API не экспонирует fitness/recursive
- Orchestrator не вызывает tiered fitness

**Программа улучшений**: 5 P0 fixes (C1-C5) — small-to-medium effort, закрывают все критические gap'ы.
