# Phase 40 — Post-Step Analysis + Research for Best Next Solution

## Что сработало

1. **MARL trainer работает end-to-end.** 4 episodes, 16 agents (4 FRIEND + 12 FOE), all active.

2. **Friend-or-foe classification корректен.** engine_01-04 = FRIEND (native), engine_05-16 = FOE (reference). Static — constitution-defined.

3. **Counterfactual credit assignment работает.** engine_16: marginal_contribution=0.0516 (positive — LLM contributes to team quality).

4. **Running average обновляется.** engine_16: individual_reward=0.3438 (average of [0.0, 0.0, 0.75, 0.625] = 1.375/4). Correct.

5. **38 тестов проходят.** Agent classification, AgentState, trainer init, episode execution, agent update, training loop, constitution compliance, determinism.

## Что НЕ сработало / требует улучшения

### Проблема 1: BASELINE agents all 0.0 reward

BASELINE policy (simulation, no real intelligence) produces quality=0.0 for all tasks. All 16 engines in BASELINE coalition get 0.0 reward. This is HONEST — simulation doesn't produce real quality.

**Решение:** Использовать real orchestrator runs (не Phase 33 BASELINE). Или normalise rewards относительно coalition mean.

### Проблема 2: Только 4 episodes

Phase 33 имеет только 4 policy-task pairs. Мало данных для MARL training.

**Решение:** Запустить больше episodes (different coalitions, different tasks). Или использовать curriculum generator для progressive difficulty.

### Проблема 3: Friend bias = 0.0 for all agents

engine_01-04 (FRIEND) have friend_bias=0.0. Это потому что в BASELINE coalition, foe_mean_quality=0.0 → friend_bias = 0.0 * 0.5 = 0.0.

**Решение:** В coalitions где foes produce real quality (LLM_SINGLE_MODEL), friends should get friend_bias. Но LLM_SINGLE_MODEL coalition = [engine_16] only (no friends).

### Проблема 4: Нет intrinsic motivation / exploration

Текущий MARL не имеет intrinsic rewards для exploration. Все rewards из task quality.

**Решение (от ресёрча):** LJIR (Chen 2023) — joint-action intrinsic reward для cooperative exploration. Iqbal — intrinsic rewards для coordinated exploration.

## Ресёрч: лучшие практики MARL (2024-2025)

Из поиска:
1. **Friend-or-Foe** (Ryu 2021, Sun 2022): biased action info — friends cooperate, foes compete. Implemented ✓.
2. **Counterfactual credit assignment** (Mar 2026, Liang, Zhao): marginal contribution via counterfactual. Implemented ✓.
3. **Intrinsic motivation** (Chen 2023, Iqbal): intrinsic rewards для exploration. NOT implemented.
4. **Policy distillation** (Tseng, cited 96): preserve structural relationships among policies. NOT implemented.
5. **MARL survey** (Ning 2024, cited 337): cooperative vs competitive settings. Both implemented ✓.

## Лучшее решение для следующего шага

**Phase 41: Red Team Adversary** — теперь, когда RLAIF (36), PBT (37), AlphaZero (38), ES (39), MARL (40) работают, Red Team добавляет adversarial pressure.

**Почему Red Team следующий:**
1. Все 5 trainers (RLAIF, PBT, AlphaZero, ES, MARL) оптимизируют for compliance/reward.
2. Red Team ATTACKS — находит vulnerabilities в constitution compliance.
3. Creates adversarial pressure — system должен defend.
4. Complement: trainers improve, red team breaks → iteratively stronger.

**Параллельно:** улучшить MARL (Phase 40.1 refinement):
- Intrinsic motivation (LJIR)
- More episodes (curriculum generator)
- Normalized rewards (relative to coalition mean)
- Policy distillation across agents

## Итог

Phase 40 — УСПЕХ. MARL friend-or-foe работает: 16 agents, counterfactual credit assignment, friend/foe bias. engine_16 (LLM) получил highest total reward (0.2509) с positive marginal contribution (0.0516). Constitution preserved (static classification, no auto-promotion).

Chain RLAIF → PBT → AlphaZero → ES → MARL работает:
- Phase 36 (RLAIF): reward signal
- Phase 37 (PBT): population evolution
- Phase 38 (AlphaZero): architecture creation
- Phase 39 (ES): fine-tuning
- Phase 40 (MARL): multi-agent credit assignment

Следующий шаг: Phase 41 (Red Team Adversary) для adversarial pressure + Phase 40.1 refinement (intrinsic motivation, more episodes).
