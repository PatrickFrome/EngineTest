# Phase 38 — Post-Step Analysis + Research for Best Next Solution

## Что сработало

1. **Self-play loop работает end-to-end.** 3 generations, 6 mechanisms extracted, 3 architectures synthesized, 5 mechanisms advanced A0→A1.

2. **Mechanism extraction корректен.** Pareto winners (BASELINE + LLM_SINGLE_MODEL) → A0_OBSERVED candidates. Library накапливается (5 unique после 3 generations — deduplication работает).

3. **Architecture synthesis работает.** 1 synthesis per generation (G+2 combinations of winning mechanisms). Каждая synthesis помечена как HYPOTHESIS (claim_ceiling = SYNTHESIS_IS_HYPOTHESIS_NOT_FACT).

4. **Constitution preserved.** Все mechanisms на A1_MECHANISM_HYPOTHESIS (не A2/A3). A2 требует gate receipt (AssimilationGate), A3 требует external promotion authority. No auto-promotion.

5. **18 тестов проходят.** Tournament, extraction, synthesis, ablation, advancement, constitution compliance — все покрыты.

## Что НЕ сработало / требует улучшения

### Проблема 1: 0 ablated mechanisms

В Phase 33 обе policies (BASELINE + LLM_SINGLE_MODEL) на Pareto frontier (non-dominated). Нет dominated policies → нет mechanisms для ablation.

**Решение:** Запустить с 4+ policies, где некоторые будут dominated. Или использовать tournament с разными task sets для создания diversity.

### Проблема 2: Только A0→A1 advancement

A1→A2 требует AssimilationGate receipt (конституционный guard). Self-play trainer не может продвигать дальше A1 без внешнего gate.

**Решение:** Интегрировать AssimilationGate (assimilation.py) в loop. Gate требует:
- A1 source mechanism
- Transfer experiment (cross-world)
- External verification

Это правильно по конституции — A2+ должен быть externally validated.

### Проблема 3: Perturbed results, не real self-play

Generations 1 и 2 используют perturbed quality values (random ±0.1). В real AlphaZero, каждая generation создаёт НОВЫЕ policies через synthesis + tournament.

**Решение:** После synthesis, создать новые ArchitecturePolicy objects из synthesized mechanisms, запустить их на tasks, получить real quality values. Это требует real orchestrator runs (rate-limited).

### Проблема 4: Synthesis не создаёт executable policies

ArchitectureSynthesizer создаёт SynthesizedArchitecture (combined_mechanisms, rationale, novelty_score), но НЕ создаёт ArchitecturePolicy. Нет bridge от synthesis → policy.

**Решение:** Добавить метод `synthesis_to_policy(synthesized_arch)` который создаёт ArchitecturePolicy с combined mechanisms как dialectic_operators.

## Ресёрч: лучшие практики self-play (2024-2025)

Из поиска:
1. **Automated curricula** (Oct 2025): sparse-reward RL требует automatic curriculum generation. MetaEngine УЖЕ имеет CurriculumGenerator (Phase 14) — нужно подключить к self-play.

2. **Self-play training paradigm** (Jul 2025): agents improve by engaging with versions of themselves. MetaEngine tournament = self-play, но нужно "versions of themselves" — т.е. новые policies из synthesis.

3. **Curriculum + AlphaZero** (West 2019, Zhou 2026): AlphaZero generates own training examples through self-play. Curriculum progressive difficulty. MetaEngine имеет CurriculumGenerator — нужно интегрировать.

4. **Autocurricula** (Nov 2025): self-play steadily increases difficulty. MetaEngine должен: easy tasks → hard tasks progressively, с tournament на каждом уровне.

## Лучшее решение для следующего шага

**Phase 39: ES (Evolution Strategies) Hyperparameter Optimizer** — теперь, когда PBT (Phase 37) эволюционирует hyperparameters и AlphaZero (Phase 38) создаёт architectures, ES даёт gradient-free optimization для точной настройки.

**Почему ES следующий:**
1. PBT использует discrete mutations (0.8/1.2 factors). ES использует continuous gradient estimation.
2. ES работает на non-differentiable objectives (quality = token overlap).
3. ES можно применить к policy hyperparameters, bridge temperature, RLAIF weights.
4. ES complement PBT: PBT = coarse search, ES = fine-tuning.

**Параллельно:** улучшить AlphaZero loop (Phase 38.1 refinement):
- Bridge synthesis → policy (создавать executable policies из synthesized mechanisms)
- Integrate AssimilationGate (A1→A2 с gate receipt)
- Integrate CurriculumGenerator (progressive difficulty)
- Real self-play (новые policies в каждой generation)

## Итог

Phase 38 — УСПЕХ. AlphaZero self-play loop работает: tournament → extract → synthesize → advance. 6 mechanisms extracted, 3 architectures synthesized, 5 advanced A0→A1. Constitution preserved (no A3 without external authority).

Chain RLAIF → PBT → AlphaZero работает:
- Phase 36 (RLAIF): reward signal
- Phase 37 (PBT): population evolution using reward
- Phase 38 (AlphaZero): architecture creation via tournament → synthesis

Следующий шаг: Phase 39 (ES) для fine-tuning + Phase 38.1 refinement (synthesis→policy bridge, AssimilationGate integration).
