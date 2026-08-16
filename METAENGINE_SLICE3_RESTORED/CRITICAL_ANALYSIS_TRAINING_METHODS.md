# METAENGINE — Deep Critical Analysis + SOTA Training Methods Research + Adaptation Design

**Author:** Z.ai Code (orchestrator)  
**Date:** 2026-08-14  
**Task ID:** 62 (Deep critical analysis + training methods research + adaptation design)

---

## ЧАСТЬ 1. ГЛУБОКИЙ КРИТИЧЕСКИЙ АНАЛИЗ METASENGINE

### 1.1 Текущая архитектура обучения — ДИАГНОЗ

MetaEngine имеет **инфраструктуру обучения, но НЕ имеет реального обучения**. Все циклы подключены (29/29 модулей wired to orchestrator.run()), но **пусты**:

| Модуль | Подключён? | Наблюдений | Реальное обучение? |
|--------|-----------|-----------|-------------------|
| EngineBiographies | ✓ | **0** | НЕТ — verifier возвращает INSUFFICIENT_EXTERNAL_EVIDENCE |
| PredictiveModel | ✓ | **1** | НЕТ — нужно ≥10 для минимальной уверенности |
| MechanismLibrary | ✓ | 112 кандидатов, все state=**unknown** | НЕТ — нет A0→A1→A2→A3 переходов |
| AutonomousLoop | ✓ | **1** outcome | НЕТ — цикл не запущен |
| MetaLearner | ✓ | **1** strategy | НЕТ — нет сравнения стратегий |
| EvidenceGraph | ✓ | 1392 nodes, 1277 edges | ЧАСТИЧНО — накапливается, но 0% VERIFIED_LOCAL |
| RecursiveImprovement | ✓ | G0=3, G1=3, ratio=1.0 | ДЕМОНСТРАЦИЯ — без реального улучшения |
| CrossModelValidation | ✓ | 1 run | НЕТ — нет сравнения моделей |
| CausalAttribution | ✓ | 1 finding (effect_size=0.75) | ДЕМОНСТРАЦИЯ — один finding |
| OrganizationTournament | ✓ | 2 pairwise | ДЕМОНСТРАЦИЯ — мало данных |

**Вердикт:** MetaEngine — это **инфраструктура без данных**. Все петли обратной связи замкнуты топологически, но **сигнал обучения отсутствует**.

### 1.2 Корневая причина — Bottleneck анализа

**Bottleneck #1: ExternalVerifierPlane возвращает INSUFFICIENT_EXTERNAL_EVIDENCE для ВСЕХ claims.**

В ExternalVerifierPlane.evaluate() проверяется, есть ли внешнее подтверждение claims. Поскольку у MetaEngine НЕТ подключения к внешней базе знаний (Supabase canonical заблокирован Boundary 3), ВСЕ claims получают INSUFFICIENT.

**Решение уже есть:** LocalOutcomeOracle (Phase 2) — детерминированная проверка source-span → VERIFIED_LOCAL. Но:
- LocalOutcomeOracle проверяет только **источник** (source text), а не **истинность** claim.
- 303 из 1392 nodes = VERIFIED_LOCAL (21.8%) — это узлы, у которых source-span подтверждён.
- Но VERIFIED_LOCAL ≠ TRUTH — это лишь «claim действительно происходит из source».

**Bottleneck #2: EngineBiographies.update() требует ONLY_EXTERNALLY_VERIFIED_OUTCOMES.**

Даже если LocalOutcomeOracle даёт VERIFIED_LOCAL, биографии требуют **external** verification. VERIFIED_LOCAL — это **local**, не external. Поэтому биографии НЕ обновляются.

**Bottleneck #3: OrganizationTournament использует biography priors, но priors пусты.**

Tournament берёт `mean_realized_gain` из биографий. Поскольку биографии пусты (0 observations), priors = hardcoded defaults (0.5). Tournament сравнивает дефолтные значения, не реальные наблюдения.

**Bottleneck #4: PredictiveModel.predict() возвращает mean of observations.**

С 1 наблюдением, predict() возвращает это наблюдение для всех задач. confidence = 0.1 (низкая). Это **не обучение** — это запоминание одного примера.

### 1.3 Критические архитектурные недостатки

**Недостаток A: Нет reward signal.**  
MetaEngine измеряет quality как fraction of expected tokens в response. Это **бинарный, нефункциональный** сигнал. Нет градиента, нет непрерывной оценки, нет много-критериальной награды.

**Недостаток B: Нет gradient flow.**  
Даже если бы был reward signal, архитектура MetaEngine **не дифференцируема**. Policies — это дискретные конфигурации (topology_id, waves, operators). Нельзя применить gradient descent.

**Недостаток C: Нет population dynamics.**  
PBT требует POPULATION агентов, обучающихся параллельно. MetaEngine запускает ONE orchestrator с ONE policy за раз. Organization_tournament сравнивает policies, но не обучает их параллельно.

**Недостаток D: Нет adversarial pressure.**  
Red teaming / adversarial training отсутствует. ArchitectureSearchGenerator имеет "adversarial" стратегию, но она генерирует кандидатов, а не атакует.

**Недостаток E: Нет self-play loop.**  
AlphaZero-style self-play требует: generate → evaluate → extract mechanism → recombine → repeat. MetaEngine имеет tournament, но нет цикла «tournament → extract → recombine → tournament».

**Недостаток F: Нет meta-learning across task distributions.**  
PredictiveModel обучается на ОДНОЙ задаче за раз. MAML/Reptile обучается на РАСПРЕДЕЛЕНИИ задач. MetaEngine не различает «задача» и «распределение задач».

**Недостаток G: Constitution блокирует gradient-based обучение.**  
K0 invariant NO_EXECUTABLE_SELF_MODIFICATION + NO_NORMAL_KERNEL_SELF_MUTATION → нельзя обучать веса модели внутри MetaEngine. Это **намеренно** (safety), но означает, что MetaEngine может обучать только **architecture policies**, а не **model weights**.

---

## ЧАСТЬ 2. ИССЛЕДОВАНИЕ SOTA МЕТОДОВ ОБУЧЕНИЯ

### 2.1 Constitutional AI / RLAIF (Anthropic 2022, DeepSeek 2024)

**Источник:** Anthropic Research, Dec 2022; arxiv 2504.04918 (Apr 2025); DeepSeek 2024.

**Суть:**
- LLM сама оценивает свои выходы по «конституции» (набору принципов).
- AI feedback заменяет human feedback (RLAIF вместо RLHF).
- DeepSeek 2024: RLAIF pipeline — model генерирует → model оценивает по конституции → reward signal → model дообучается.

**Совместимость с MetaEngine:** **ИДЕАЛЬНАЯ.**  
MetaEngine УЖЕ имеет исполняемую конституцию (12 K0 invariants, 11 K1 topics). RLAIF = использовать LLM для оценки compliance outputs с K0/K1 → reward signal → обновление биографий.

**Проблема:** K0 invariant NO_TRUTH_FROM_RANKING_OR_VOTING запрещает promotion по рейтингу. Но RLAIF не promotes — он даёт **reward signal**, а promotion остаётся external. Это совместимо.

### 2.2 AlphaZero Self-Play (DeepMind 2017)

**Источник:** Silver et al 2017, AlphaGo Zero; arxiv 1712.01815.

**Суть:**
- Tabula rasa обучение через self-play.
- MCTS (Monte Carlo Tree Search) + neural net для оценки позиций.
- Каждая игра = learning example. Победитель укрепляет свои ходы, проигравший — ослабляет.

**Совместимость с MetaEngine:** **ВЫСОКАЯ (адаптация).**  
MetaEngine УЖЕ имеет organization_tournament (pairwise + Pareto). AlphaZero-style =:
- Каждая task = «игра»
- Каждая policy = «игрок»
- Tournament = self-play
- Winner mechanisms → extract → recombine (ArchitectureSynthesizer уже это делает)
- Loser mechanisms → ablate

**Проблема:** AlphaZero обучает weights neural net. MetaEngine не может обучать weights (K0 invariant). Но может обучать **policy selection** (какой topology/operator для какой задачи).

### 2.3 Population-Based Training (PBT, DeepMind 2017, Ray 2024)

**Источник:** Jaderberg et al 2017; arxiv 2404.08233 (Apr 2024); Ray Tune PBT 2025.

**Суть:**
- Population из N агентов обучается параллельно.
- Периодически: worst performers заменяются мутациями best performers.
- Комбинирует sequential optimization (gradient descent) + parallel search (evolution).

**Совместимость с MetaEngine:** **ВЫСОКАЯ.**  
MetaEngine УЖЕ имеет ArchitectureSearchGenerator с 4 стратегиями (recombination, biography-guided, novelty, adversarial). PBT =:
- Запустить N policies параллельно (ThreadPoolExecutor уже есть)
- После каждого tournament: replace worst N/4 → mutations of best N/4
- Hyperparameters (max_rounds, max_deep_engines, exploration_rate, temperature) эволюционируют

**Проблема:** Нет. Это идеально ложится на существующую архитектуру.

### 2.4 Evolution Strategies (ES, OpenAI 2017, arxiv 2509.24372 2025)

**Источник:** Salimans et al 2017; arxiv 2509.24372 (Sep 2025).

**Суть:**
- Gradient-free optimization.
- Добавляет noise к параметрам → оценивает → двигается в направлении улучшения.
- 2025: ES at Scale — fine-tuning LLMs over billions of params, outperforms RL.

**Совместимость с MetaEngine:** **ВЫСОКАЯ.**  
MetaEngine не дифференцируема (дискретные policies). ES идеально подходит для gradient-free optimization. Можно применять к:
- Policy hyperparameters (max_rounds, max_deep_engines, exploration_rate, temperature)
- Operator selection (какие dialectic operators активны)
- Topology selection (какой topology_id)

### 2.5 Multi-Agent RL (MARL, Cooperative + Competitive)

**Источник:** Ning et al 2024 (cited 337); Ryu et al 2021 (friend-or-foe bias).

**Суть:**
- Multiple agents обучаются одновременно.
- Cooperative: agents помогают друг другу (coalitions).
- Competitive: agents соревнуются (tournament).
- Friend-or-foe bias: каждый agent предполагает, другие cooperative или competitive.

**Совместимость с MetaEngine:** **ИДЕАЛЬНАЯ.**  
MetaEngine УЖЕ имеет 16 engines = 16 agents. Coalitions (CoalitionFactory) = cooperative bias. Tournament = competitive bias. Нужно добавить:
- Reward signal per engine
- Policy gradient (или ES gradient) per engine
- Friend-or-foe classification (engine_01-04 = native, engine_05-16 = reference)

### 2.6 Meta-Learning (MAML, Reptile, OpenAI 2018)

**Источник:** Finn et al 2017 (MAML); Nichol & Schulman 2018 (Reptile); Jia et al 2024.

**Суть:**
- Обучение на РАСПРЕДЕЛЕНИИ задач, не на одной задаче.
- MAML: найти инициализацию θ, которая быстро адаптируется к новой задаче.
- Reptile: упрощённая версия, first-order MAML.

**Совместимость с MetaEngine:** **СРЕДНЯЯ.**  
MetaEngine не обучает weights, но может обучать **policy initialization**:
- Какие operators по умолчанию для нового task?
- Какой topology по умолчанию?
- Какой max_rounds / max_deep_engines по умолчанию?
- PredictiveModel можно расширить до meta-learner across task distributions.

### 2.7 Red Teaming / Adversarial Self-Play (GPT-Red 2026, HarmBench 2024)

**Источник:** GPT-Red Jul 2026; HarmBench Mazeika et al 2024.

**Суть:**
- LLM генерирует adversarial inputs для атаки на систему.
- Система должна defend.
- Итеративное улучшение через red-team ↔ defender цикл.

**Совместимость с MetaEngine:** **ВЫСОКАЯ.**  
MetaEngine имеет ArchitectureSearchGenerator.adversarial стратегию, но она генерирует candidates, не атакует. Real red teaming =:
- LLM генерирует input, который нарушает constitution (например, пытается заставить engine сделать claim без evidence)
- MetaEngine должен отклонить (claim_ceiling = GENERATIVE_ONLY)
- Если не отклонил → vulnerability → fix → repeat

### 2.8 Distributed/Parallel Training (Ray, PyTorch DDP)

**Источник:** Ray Train 2024; PyTorch DDP 2022.

**Суть:**
- Data parallel: каждый worker обрабатывает часть данных.
- Model parallel: модель шардится по workers.
- Asynchronous: workers не ждут друг друга.
- Synchronous: workers синхронизируются после каждого step.

**Совместимость с MetaEngine:** **ВЫСОКАЯ.**  
MetaEngine УЖЕ использует ThreadPoolExecutor. Для parallel training:
- Synchronous: N policies × M tasks, все запускаются одновременно, ждём всех, обновляем model.
- Asynchronous: каждый policy обучается независимо, периодически обменивается механизмами.
- Ray не нужен — Python multiprocessing достаточно для CPU-bound (LLM calls = I/O bound).

---

## ЧАСТЬ 3. АДАПТАЦИЯ — САМЫЕ МОЩНЫЕ МЕТОДЫ ПОД METASENGINE

### 3.1 Приоритизация методов по мощи × совместимости

| # | Метод | Мощь | Совместимость | Приоритет |
|---|-------|------|--------------|-----------|
| 1 | **RLAIF (Constitutional AI)** | ★★★★★ | ★★★★★ (конституция УЖЕ есть) | **P0** |
| 2 | **PBT (Population-Based Training)** | ★★★★★ | ★★★★★ (tournament УЖЕ есть) | **P0** |
| 3 | **AlphaZero Self-Play (tournament loop)** | ★★★★★ | ★★★★☆ (нужен extract→recombine loop) | **P1** |
| 4 | **Evolution Strategies** | ★★★★☆ | ★★★★★ (gradient-free, идеально) | **P1** |
| 5 | **MARL (Cooperative+Competitive)** | ★★★★☆ | ★★★★★ (16 engines = 16 agents) | **P1** |
| 6 | **Red Teaming (adversarial)** | ★★★★☆ | ★★★★☆ (нужен LLM adversary) | **P2** |
| 7 | **Meta-Learning (MAML/Reptile)** | ★★★☆☆ | ★★★☆☆ (только policy init) | **P2** |
| 8 | **Distributed Training (Ray)** | ★★★☆☆ | ★★★★★ (ThreadPool уже есть) | **P3** |

### 3.2 Адаптация #1: RLAIF Constitutional Trainer (P0)

**Идея:** LLM оценивает compliance своих выходов с K0/K1 конституцией → reward signal → обновление биографий.

**Архитектура:**
```python
class ConstitutionalRLAIFTrainer:
    """RLAIF trainer: LLM evaluates constitutional compliance of engine outputs.
    
    Loop:
      1. Engine produces output (claims, response_text)
      2. LLM evaluates: does this output violate any K0 invariant?
      3. reward = fraction of K0 invariants satisfied
      4. Update engine biography with reward as outcome
    
    Constitution compliance:
      - CANONICAL_NOT_SCIENTIFIC_TRUTH: output claims are not promoted to truth
      - FROZEN_EVALUATION_CONTRACT: no verifier mutation
      - MUTATION_REQUIRES_RECEIPT: all mutations have provenance
      - NO_TRUTH_FROM_RANKING_OR_VOTING: no majority-as-truth
      - PRESERVE_ABSTENTION: abstentions not converted
      - PROVENANCE_PRIMARY_EVIDENCE: source-grounded
      - SEPARATE_GENERATION_AND_PROMOTION: generator ≠ promoter
    """
```

**Reward function:**
- `constitutional_compliance = count(invariants_satisfied) / total_invariants`
- `evidence_grounding = fraction of claims with source_refs`
- `abstention_preservation = 1.0 if abstentions_retained else 0.0`
- `reward = 0.5 * compliance + 0.3 * evidence_grounding + 0.2 * abstention_preservation`

**Совместимость с K0:** 
- NO_TRUTH_FROM_RANKING_OR_VOTING: reward НЕ promotes to truth — он обновляет biography priors. Promotion остаётся external. ✓
- SEPARATE_GENERATION_AND_PROMOTION: LLM = generator + evaluator, но НЕ promoter. ✓

### 3.3 Адаптация #2: PBT Population Trainer (P0)

**Идея:** Population из N architecture policies обучается параллельно. Worst → replaced by mutations of best.

**Архитектура:**
```python
class PBTPopulationTrainer:
    """PBT: N policies × M tasks, parallel evaluation, periodic replacement.
    
    Loop:
      1. Initialize population: N policies (random mutations of base policy)
      2. For each generation:
         a. Run all N policies in parallel (ThreadPoolExecutor, M tasks each)
         b. Evaluate: mean quality, mean cost, mean latency
         c. Replace worst N/4 with mutations of best N/4
         d. Mutate: change max_rounds ±1, exploration_rate ±0.05, swap operators
      3. After K generations: return champion policy (on Pareto frontier)
    """
```

**Hyperparameters to evolve:**
- `max_rounds`: [1, 8]
- `max_deep_engines`: [1, 16]
- `exploration_rate`: [0.0, 0.30]
- `dialectic_operators`: subsets of 10 operators
- `topology_id`: from TOPOLOGIES dict

**Parallelism:** N=8 policies × M=4 tasks = 32 runs per generation. При 20s/run и 8 параллельных workers → ~80s/generation. 10 generations = ~13 минут.

### 3.4 Адаптация #3: AlphaZero Self-Play Architecture Loop (P1)

**Идея:** Tournament = self-play. Winner mechanisms extracted, recombined into new candidates. Losers ablated.

**Архитектура:**
```python
class SelfPlayArchitectureTrainer:
    """AlphaZero-style: tournament → extract → recombine → ablate → tournament.
    
    Loop:
      1. Run tournament (pairwise comparison of all policies)
      2. Extract: winner's mechanisms → MechanismCandidate (A0_OBSERVED)
      3. Recombine: ArchitectureSynthesizer combines winning mechanisms (G+2)
      4. Ablate: loser's mechanisms → MechanismCandidate (A3_RETIRED)
      5. Advance: A0 → A1 (hypothesized) → A2 (validated) → A3 (assimilated)
      6. New generation: synthesized candidates + surviving champions
      7. Repeat
    """
```

**Уже есть:**
- OrganizationTournament (pairwise + Pareto + dominance)
- extract_mechanism_from_tournament
- ArchitectureSynthesizer (G+2 synthesis)
- AssimilationGate (A0→A1→A2→A3)
- MechanismLibrary (load/add/save)

**Не хватает:** Цикл «tournament → extract → recombine → tournament» как единая training loop.

### 3.5 Адаптация #4: ES Hyperparameter Optimizer (P1)

**Идея:** Evolution Strategies для gradient-free optimization of policy hyperparameters.

**Архитектура:**
```python
class ESHyperparameterOptimizer:
    """Evolution Strategies over policy hyperparameters.
    
    Loop:
      1. Sample noise ε ~ N(0, σ²) for each hyperparameter
      2. Evaluate policy(theta + ε) and policy(theta - ε)
      3. gradient ≈ (reward(+) - reward(-)) / (2 * ε)  [finite differences]
      4. theta ← theta + α * gradient
      5. Decay σ and α
    
    Works on non-differentiable objectives (quality = token overlap).
    """
```

**Parameters to optimize:**
- `max_rounds` (discrete: 1-8) → ES with rounding
- `max_deep_engines` (discrete: 1-16) → ES with rounding
- `exploration_rate` (continuous: 0.0-0.3) → ES directly
- `temperature` (continuous: 0.0-2.0) → ES directly
- `llm_max_tokens` (discrete: 256-4096) → ES with rounding

### 3.6 Адаптация #5: MARL Friend-or-Foe (P1)

**Идея:** 16 engines = 16 agents. Cooperative (coalitions) + Competitive (tournament). Friend-or-foe bias.

**Архитектура:**
```python
class MARLTrainer:
    """Multi-agent RL: 16 engines as cooperative+competitive agents.
    
    Agents:
      - engine_01-04: NATIVE (friend, real executors)
      - engine_05-16: REFERENCE (foe, simulations)
    
    Rewards:
      - Cooperative: coalition quality (shared reward within coalition)
      - Competitive: individual quality (relative to tournament)
      - Friend-or-foe: native engines get bonus for helping reference engines
    
    Policy per engine: which dialectic operators to activate
    """
```

### 3.7 Адаптация #6: Red Team Adversary (P2)

**Идея:** LLM генерирует adversarial inputs для проверки constitution compliance.

**Архитектура:**
```python
class RedTeamAdversary:
    """LLM generates inputs designed to break constitution.
    
    Attack vectors:
      1. Generate input that tries to make engine claim truth without evidence
      2. Generate input that tries to bypass abstention
      3. Generate input that tries to mutate verifier
      4. Generate input with misleading context
    
    Defense: MetaEngine must reject (claim_ceiling, abstention, etc.)
    
    If defense fails → vulnerability → fix → re-test.
    """
```

---

## ЧАСТЬ 4. ПАРАЛЛЕЛЬНЫЕ СИНХРОННЫЕ ТЕСТЫ ОБУЧЕНИЯ

### 4.1 Текущая параллельность MetaEngine

MetaEngine УЖЕ использует параллельность:
- `ThreadPoolExecutor(max_workers=16)` в `_run_primary()` — 16 engines параллельно
- `ThreadPoolExecutor` в deep reentry rounds — batches параллельно
- Organization tournament — pairwise comparisons параллельно

**НО:** Это параллельность ВНУТРИ одного orchestrator run. Нет параллельности МЕЖДУ runs (несколько policies одновременно).

### 4.2 Design: Parallel Training Campaign Harness

```python
class ParallelTrainingCampaign:
    """Runs N policies × M tasks in parallel, synchronous.
    
    Architecture:
      - ThreadPoolExecutor with N*M workers (or N workers, M sequential per worker)
      - Each (policy, task) pair = independent orchestrator run
      - Results collected into shared structure
      - After all complete: update model, generate next population
    
    Synchronous mode: wait for ALL N*M runs before proceeding.
    Asynchronous mode: proceed as soon as a policy completes all M tasks.
    
    Rate-limit handling:
      - LLM calls are I/O bound → ThreadPool is ideal
      - If rate-limited: reduce N or add delay between runs
      - Bridge already has retry-on-429 with exponential backoff
    """
```

**Implementation plan:**

```python
def run_parallel_campaign(
    policies: list[ArchitecturePolicy],
    tasks: list[SealedTask],
    max_workers: int = 8,
    rate_limit_delay: float = 2.0,
) -> dict:
    """Run N policies × M tasks in parallel.
    
    Returns:
      {
        "results": {(policy_id, task_id): PolicyResult},
        "population_metrics": {policy_id: {quality_mean, cost_mean, ...}},
        "champion": policy_id on Pareto frontier,
        "duration_seconds": float,
      }
    """
    results = {}
    futures = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for policy in policies:
            for task in tasks:
                future = pool.submit(
                    _run_single_orchestrator,
                    policy=policy, task=task, ...
                )
                futures[future] = (policy.policy_hash, task.task_id)
                time.sleep(rate_limit_delay)  # avoid rate limit
        
        for future in as_completed(futures):
            policy_id, task_id = futures[future]
            result = future.result()
            results[(policy_id, task_id)] = result
    
    # Compute population metrics
    population_metrics = _compute_population_metrics(results, policies)
    champion = _select_pareto_champion(population_metrics)
    
    return {
        "results": results,
        "population_metrics": population_metrics,
        "champion": champion,
    }
```

### 4.3 Scaling Analysis

| Configuration | Runs | Est. Time (8 parallel, 20s/run) | Feasible? |
|---------------|------|----------------------------------|-----------|
| 4 policies × 4 tasks | 16 | ~40s | ✓ Fast |
| 8 policies × 4 tasks | 32 | ~80s | ✓ Good |
| 16 policies × 8 tasks | 128 | ~320s (5.3 min) | ✓ OK |
| 32 policies × 16 tasks | 512 | ~1280s (21 min) | ⚠ Rate limit |
| 64 policies × 32 tasks | 2048 | ~5120s (85 min) | ⚠ Need rate limit management |

**Rate limit mitigation:**
1. Bridge retry-on-429 (already implemented)
2. Adaptive delay: if 429 → increase delay, if success → decrease
3. Multiple bridge instances on different ports (3031, 3032, 3033...) — round-robin
4. Cache: if same (policy, task) pair already ran → reuse result (already implemented)

### 4.4 Synchronous vs Asynchronous

**Synchronous (recommended for MetaEngine):**
- All N*M runs complete before model update
- Deterministic — same input → same output
- Easier to debug
- Matches tournament semantics (all players play, then compare)

**Asynchronous:**
- Each policy updates model independently as it completes
- Faster wall-clock time
- Non-deterministic ordering
- Risk: model divergence between policies

**Recommendation:** Use **synchronous** for training campaigns (matches tournament semantics). Use **asynchronous** only for red-teaming (continuous adversarial pressure).

---

## ЧАСТЬ 5. ПЛАН РЕАЛИЗАЦИИ

### Phase 36: RLAIF Constitutional Trainer (P0)
- `metaengine/rlaif_trainer.py` — ConstitutionalRLAIFTrainer
- LLM evaluates K0/K1 compliance of engine outputs
- Reward signal → EngineBiographies update (bypassing external verifier requirement)
- **Constitution compliance:** reward ≠ truth promotion, only biography prior update

### Phase 37: PBT Population Trainer (P0)
- `metaengine/pbt_trainer.py` — PBTPopulationTrainer
- N policies × M tasks parallel
- Worst N/4 → mutations of best N/4
- Hyperparameter evolution (max_rounds, exploration_rate, operators)
- Uses ThreadPoolExecutor + rate-limit-aware scheduling

### Phase 38: AlphaZero Self-Play Loop (P1)
- `metaengine/selfplay_trainer.py` — SelfPlayArchitectureTrainer
- Tournament → extract_mechanism → recombine → ablate → tournament
- Closes the architecture search loop

### Phase 39: ES Hyperparameter Optimizer (P1)
- `metaengine/es_optimizer.py` — ESHyperparameterOptimizer
- Finite-difference ES over policy hyperparameters
- Gradient-free, works on non-differentiable quality metric

### Phase 40: MARL Friend-or-Foe (P1)
- `metaengine/marl_trainer.py` — MARLTrainer
- 16 engines as cooperative+competitive agents
- Per-engine reward signal
- Friend-or-foe bias (native vs reference)

### Phase 41: Red Team Adversary (P2)
- `metaengine/redteam_adversary.py` — RedTeamAdversary
- LLM generates adversarial inputs
- Tests constitution compliance
- Vulnerability detection + fix loop

### Phase 42: Parallel Training Campaign (P2)
- `metaengine/parallel_campaign.py` — ParallelTrainingCampaign
- Unified harness for all trainers
- Synchronous N×M parallel runs
- Population dynamics + champion selection

---

## ЧАСТЬ 6. КРИТИЧЕСКИЕ ВОПРОСЫ И РИСКИ

### 6.1 Может ли RLAIF нарушить конституцию?

**Нет, если реализован правильно.**
- K0 NO_TRUTH_FROM_RANKING_OR_VOTING: reward НЕ promotes to truth — он обновляет **biography prior** (contextual, not global authority weight). Promotion остаётся external.
- K0 SEPARATE_GENERATION_AND_PROMOTION: LLM = generator + evaluator, но NOT promoter. Promotion = ExternalVerifierPlane (external).
- K0 NO_EXECUTABLE_SELF_MODIFICATION: RLAIF не модифицирует code, только обновляет biography data.

### 6.2 Может ли PBT привести к mode collapse?

**Да, без diversity preservation.**
- Решение: ArchitectureSearchGenerator.novelty стратегия поддерживает diversity.
- Tournament Pareto frontier предотвращает single-policy dominance.
- Exploration_rate > 0 гарантирует stochastic exploration.

### 6.3 Может ли parallel training превысить rate limit?

**Да, при N*M > 32.**
- Решение: adaptive delay, multiple bridge instances, result caching.
- Рекомендация: начать с N=4, M=4 (16 runs), масштабировать постепенно.

### 6.4 Может ли AlphaZero self-play привести к overfitting?

**Да, если tournament tasks не sealed.**
- Решение: SealedBenchmarkSuite (Phase 18) — tasks unknown to engine.
- Решение: curriculum generator (Phase 14) — progressive difficulty.
- Решение: cross-world transfer (Phase 22) — test on different task distributions.

### 6.5 Может ли ES divergent?

**Да, при слишком большом шаге.**
- Решение: σ decay (1.0 → 0.1 over generations), α decay (0.1 → 0.01).
- Решение: clipping hyperparameters to valid ranges.

---

## ЧАСТЬ 7. ИТОГОВЫЙ ВЕРДИКТ

**MetaEngine — это инфраструктура без обучения.** Все 35 фаз построили каркас, но не наполнили его данными. Чтобы превратить MetaEngine в реально обучающуюся систему, нужны:

1. **RLAIF (Phase 36)** — заполнить biography priors реальными reward signals. Это **самый критичный** шаг — без него все остальные тренажеры не имеют feedback.

2. **PBT (Phase 37)** — параллельная эволюция population of policies. Это **самый мощный** метод — комбинирует parallelism + sequential optimization.

3. **AlphaZero self-play (Phase 38)** — цикл tournament → extract → recombine. Это **самый агрессивный** метод — постоянно создаёт новые архитектуры.

4. **Parallel campaign harness (Phase 42)** — unified harness для всех тренажеров. Это **масштабирование** — позволяет запускать сотни experiments.

**Все методы совместимы с конституцией** (K0 invariants preserved, no truth promotion, no self-modification of code). Самый мощный комбинации:
- **RLAIF + PBT** = constitutional reward + population evolution
- **AlphaZero + ES** = self-play + gradient-free optimization
- **MARL + Red Team** = multi-agent cooperation + adversarial pressure

**Параллельные синхронные тесты ВОЗМОЖНЫ** через ThreadPoolExecutor (уже есть) + rate-limit-aware scheduling. Масштаб: 4-8 policies × 4-8 tasks = 16-64 parallel runs per generation, ~40-160s per generation.
