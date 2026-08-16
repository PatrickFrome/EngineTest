# Destruktion 4.0 — External Hermeneutic Validation 0.8

Этап 0.8 сознательно **не добавляет новый GX, operator family или автоматическую мутацию**. Его задача — вынести оценку за пределы внутреннего языка движка.

## Что новый слой проверяет

1. DAE-предсказания уже заморожены CORE benchmark-ом.
2. Как минимум один сильный внешний comparator генерирует решения **до gold** и подтверждает, что не видел DAE outputs, raw annotations и gold.
3. Независимый challenge-author до gold замораживает semantic adversarial suite.
4. CORE отдельно проводит две или более blind human annotations, agreement и adjudicated gold.
5. После freeze все системы проходят один и тот же adversarial suite.
6. Сравнение идёт по нескольким независимым измерениям; единый scalar winner запрещён.

## Семь обязательных adversarial phenomena

- `NEGATION`
- `QUOTED_OPPONENT`
- `ATTRIBUTION_SHIFT`
- `MODALITY_WEAKENING`
- `PARAPHRASE`
- `TRANSLATION`
- `DECOY_TERMINOLOGY`

## Минимальный рабочий цикл

```bash
# 1. CORE: заморозить benchmark и DAE predictions
node bin/destruktion.mjs benchmark-init \
  ./path/to/expert_cycle.json \
  --out ./benchmark

# 2. Studio: создать внешний validation campaign
node studio/studio.mjs validation:init ./benchmark --out ./external-validation

# 3. Независимо заполнить:
# external-validation/templates/external_system.template.json
# external-validation/templates/semantic_challenge.template.json

# 4. До появления gold заморозить external systems + challenge
node studio/studio.mjs validation:freeze ./external-validation \
  --system ./frontier-baseline.json \
  --system ./scholarly-prompt-baseline.json \
  --challenge ./semantic-challenge.json

# 5. CORE: после двух blind annotations заморозить gold и выполнить evaluation
node bin/destruktion.mjs benchmark-evaluate ./benchmark \
  --annotations ./annotations \
  --gold ./gold.json \
  --out ./core-benchmark-evaluation

# 6. После freeze выполнить challenge всеми системами и заполнить templates
# external-validation/post_freeze_templates/*.template.json

# 7. Сравнить DAE и внешние системы
node studio/studio.mjs validation:evaluate ./external-validation \
  --gold ./gold.json \
  --core-result ./core-benchmark-evaluation/BENCHMARK_RESULT.json \
  --adversarial ./dae.semantic_challenge_results.json \
  --adversarial ./frontier.semantic_challenge_results.json \
  --adversarial ./scholarly.semantic_challenge_results.json \
  --out ./external-validation-result
```

## Что считается сравнением

Для каждого system считаются:

- Macro-F1;
- balanced accuracy;
- dangerous overpromotion rate;
- calibration ECE;
- coverage;
- adversarial pass rate.

Эти значения **не складываются в одну метрику**. Используется Pareto non-dominance. Возможные сильные исходы:

- `DAE_DOMINATED_ON_FROZEN_SAMPLE`
- `DAE_PARETO_NONDOMINATED_ON_FROZEN_SAMPLE`
- `TRADEOFF_UNRESOLVED_ON_FROZEN_SAMPLE`

Даже первый или второй исход относится только к замороженной выборке.

## Anti-self-confirmation

Слой намеренно блокирует:

- external comparator, который видел DAE output;
- comparator, который видел gold или human annotations;
- semantic challenge, автор которого видел DAE predictions или gold;
- изменение external predictions после freeze;
- изменение challenge после freeze;
- изменение identity-полей campaign после freeze;
- evaluation без штатного CORE `BENCHMARK_RESULT.json`;
- evaluation без adversarial results для **каждой** сравниваемой системы.

100% DAE↔gold agreement не считается доказательством. Если внешний frozen comparator расходится с DAE, такое совпадение автоматически создаёт `EXACT_DAE_GOLD_MATCH_REQUIRES_PREDICTION_IMPRINT_REVIEW`.

## Текущий пример

`examples/external-validation-0.8/` — реальный scaffold, построенный из текущего Heidegger expert-cycle. В нём 22 units из двух независимых expert-cycle run IDs при frozen minimum 80, поэтому он **UNDERPOWERED** и остаётся `OPEN_FOR_EXTERNAL_SYSTEMS`. Никакие внешние labels или baseline results не сфабрикованы.

## Claim ceiling

0.8 создаёт инфраструктуру внешней фальсификации, но сам по себе не является внешней валидацией Destruktion. Для научного вывода нужны реальные независимые annotators, реальный adjudicated gold и реально запущенные внешние comparators.
