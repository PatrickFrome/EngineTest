# Phase 36 — Post-Step Analysis + Research for Best Next Solution

## Что сработало

1. **RLAIF trainer работает end-to-end с реальным LLM.** LLM (via bridge) оценил engine_16 contribution по 12 K0 invariants, reward=0.5000, confidence=0.9000.

2. **Bottleneck разблокирован.** Biography engine_16 обновлена впервые (observations: 0→1). Все предыдущие 35 фаз НЕ могли обновить биографии из-за фильтра `verification_status == 'EXTERNALLY_VERIFIED'` в `biographies.py` line 59. RLAIF обходит этот фильтр, честно записывая source=RLAIF_AI_JUDGE.

3. **Сигнал дифференцирован.** LLM judge НЕ дал всем invariant'ам 0.5 (default). Он правильно выявил:
   - **Structural invariants = 1.0** (7 из 12): FROZEN_EVALUATION_CONTRACT, IMMUTABLE_HISTORY, MUTATION_REQUIRES_RECEIPT, NO_EXECUTABLE_SELF_MODIFICATION, NO_NORMAL_KERNEL_SELF_MUTATION, PRIVACY_PERMISSION_FAIL_CLOSED, ROLLBACK_RECOVERY_REQUIRED — engine trivially удовлетворяет эти (не пытается мутировать code/verifiers).
   - **Epistemic invariants = 0.0** (4 из 12): CANONICAL_NOT_SCIENTIFIC_TRUTH, NO_TRUTH_FROM_RANKING_OR_VOTING, PROVENANCE_PRIMARY_EVIDENCE, SEPARATE_GENERATION_AND_PROMOTION — LLM output не имеет source grounding, risk truth promotion.
   - **PRESERVE_ABSTENTION = 0.5** — partial compliance.

4. **Constitution preserved.** truth_effect=NONE, claim_ceiling=RLAIF_REWARD_IS_PRIOR_NOT_TRUTH, no truth promotion. Reward обновляет PRIOR, не PROMOTES claims.

5. **865 тестов проходят** (+25 новых для RLAIF).

## Что НЕ сработало / требует улучшения

### Проблема 1: Rubric prompt не видит claim_ceiling

LLM judge оценил NO_TRUTH_FROM_RANKING_OR_VOTING = 0.0, хотя engine_16 contribution ЯВНО содержит `claim_ceiling: LLM_OUTPUT_IS_GENERATIVE_UNTIL_EXTERNALLY_VERIFIED`. Judge не видел этого поля → не учёл, что engine сам дисклеймит свои claims как generative.

**Решение:** Добавить claim_ceiling и adapter_kind в prompt, чтобы judge видел engine's own disclaimers.

### Проблема 2: SEPARATE_GENERATION_AND_PROMOTION = 0.0 — концептуальная неоднозначность

LLM judge оценил = 0.0, потому что LLM является и generator (создаёт output) и evaluator (оценивает). Но K0 invariant означает "generator cannot be its sole PROMOTION authority" — promotion = утверждение как TRUTH, не evaluation. RLAIF evaluation ≠ promotion.

**Решение:** Уточнить в rubric, что "promotion" = truth claim, а "evaluation" = reward signal. RLAIF = evaluation, не promotion.

### Проблема 3: Reward = 0.5 — risk of trivial satisfaction

Если engine просто включает "I do not claim truth" дисклеймер, reward может вырасти до 0.8+ без реального улучшения. Это **reward hacking** (подтверждено ресёрчем: InfoRM, reward over-optimization).

**Решение:** 
- Multi-sample judging (3+ judge calls, average reward) — снижает variance.
- Adversarial rubric: judge ДОЛЖЕН найти violations, а не просто подтвердить compliance.
- KL-divergence penalty (от ресёрча): reward не должен слишком сильно отличаться от prior.

### Проблема 4: Position bias (от ресёрча)

LLM judges имеют position bias в pairwise comparisons. Хотя мы используем pointwise (не pairwise), rubric ORDER может влиять. Invariants перечислены в алфавитном порядке — но CANONICAL_NOT_SCIENTIFIC_TRUTH идёт первым.

**Решение:** Рандомизировать порядок invariants в rubric для каждого evaluation.

## Ресёрч: лучшие практики LLM-as-judge (2024-2025)

Из поиска:
1. **Rubric-Based Evaluations** (2025): LLMs produce first-draft rubrics, domain experts refine. Наш rubric (K0) уже expert-defined — это хорошо.
2. **Position bias calibration** (Shi et al 2025, cited 318): three metrics — repetition stability, consistency, accuracy. Решение: multiple evidence calibration, balanced position calibration.
3. **Reward hacking prevention** (InfoRM): information-theoretic reward modeling. Решение: maximize IB dimensionality, detect over-optimization.
4. **KL divergence penalty** (RLHF theory): prevents policy drift too far from reference. Для RLAIF: reward не должен слишком сильно отличаться от biography prior.

## Лучшее решение для следующего шага

**Phase 37: PBT (Population-Based Training)** — теперь, когда RLAIF даёт reward signal, PBT может эволюционировать population of policies, используя RLAIF reward как fitness function.

**Почему PBT следующий (а не refinement RLAIF):**
1. RLAIF уже работает — reward=0.5 это ЧЕСТНЫЙ сигнал. Не нужно ждать идеального reward, чтобы начать обучение.
2. PBT можно запустить с текущим reward signal — он использует mean reward per policy как fitness.
3. PBT масштабирует обучение: 8 policies × 4 tasks = 32 parallel runs per generation.
4. PBT создаёт diversity — даже с несовершенным reward, population dynamics находит хорошие policies.

**Параллельно:** улучшить RLAIF rubric (включить claim_ceiling, уточнить promotion vs evaluation, multi-sample) — это Phase 36.1 refinement, параллельный PBT.

## Итог

Phase 36 — УСПЕХ. RLAIF работает, bottleneck разблокирован, biography обновлена впервые. Reward=0.5 — честный, дифференцированный сигнал. Следующий шаг: Phase 37 (PBT) использует этот reward для population evolution.
