# MetaEngine 16X 2.3 — отчёт о реализации

## Итог

MetaEngine переведён с внутренней самооценки на контролируемое outcome-based обучение архитектурных политик. Система больше не принимает число типов transformations, causal depth, topology diversity или собственный ensemble score за доказательство улучшения.

Главный результат — не декларация «достигнут уровень лучших аналогов», а работающий контур, который способен честно доказать или отвергнуть конкретное обновление. В локальной кампании два поколения были продвинуты, третье осталось на прежнем champion, поскольку нового положительного эффекта не было.

## Реализованные рекомендации

| Рекомендация аудита | Реализация 2.3 |
|---|---|
| Typed handoff терялся после `pressures[:16]` | Handoff передаётся отдельным объектом, проверяется по hash, компилируется перед untrusted source и связан с receipt/cache key |
| `TYPE_MAP` фабриковал transformations | Статический путь удалён; transformations извлекаются только из фактического canonical/native output |
| `realized_gain` был циклической формулой | Разделены `predicted_gain` и `observed_outcome`; без oracle outcome равен `null` |
| Grounding награждал требование проверки | Verifier проверяет точные границы и SHA-256 source spans |
| Fake Elo | Удалён; pairwise ranking сравнивает только внешние outcomes, unverified comparisons являются ties |
| Hardcoded independence | Заменена нейтральным prior; реальная независимость должна поступать из matched external ablations |
| Reference adapters считались полноценными engines | Статусы и отчёты явно разделяют четыре native executors и 12 reference simulations |
| Biography училась на самооценке | Обновление допускает только `EXTERNALLY_VERIFIED` observations; missing не превращается в ноль |
| Неконтролируемое самообновление | Введена декларативная policy algebra, immutable boundary, generation freeze, CAS promotion и rollback |
| Structural nonlinearity gaming | Прокси помечены diagnostic-only и исключены из promotion |
| Нет герменевтического content loop | Реализован typed dialectical graph из 10 операторов с rivals, horizons, counterfactuals, falsifiers и residual tensions |
| Нет продуктового synthesis | Добавлен `AUDITABLE_SYNTHESIS.json`, сохраняющий rival readings и unresolved claims |
| Нет telemetry | Hash-chained telemetry; неизвестные tokens/USD остаются missing |
| Cache можно было подменить | Payload hash проверяется на чтении; policy/handoff/verifier/guardrail snapshots входят в key |
| Слабая process safety | Проверяется release hash исполняемых lineage-файлов; timeout убивает всю process group; secrets redacted |
| Prompt injection смешивался с control plane | Handoff/control размещены отдельно; источник явно untrusted и не влияет на permissions/policy |
| Прямая репликация без outbox | Добавлен content-addressed replication outbox; URL БД убран из argv |
| Нет схемы policy/outcome/promotion | Миграции 2.2/2.3 применены к единственной канонической БД Supabase: forced RLS, writer policies, champion CAS, rollback и verifier ledgers |

## Результаты параллельной эволюции

Запущено 7,200 изолированных миров: 3 поколения × 25 политик (champion + 24 candidates) × 48 задач × 2 seed. Фактический предел одновременно выполняемых миров был установлен в 8 по доступным 9 CPU.

Использовались шесть классов задач: parallel, sequential, adversarial, tool-like, hermeneutic и evidence. Внутри поколения обучение заморожено. После barrier применяется successive halving 24→8→3 и paired holdout evaluation.

1. Первое поколение добавило horizon disclosure, semantic counterfactual и genealogical return; скорректированная нижняя граница эффекта +0.047917.
2. Второе добавило double hermeneutic, sublation with residue и operator mutation; нижняя граница +0.016528.
3. Третье не нашло улучшения и сохранило champion. Это принципиально важно: система научилась не обновляться при отсутствии доказанного эффекта.

## Что означает «качественно иной уровень»

В 2.3 это не рост количества узлов. Переход фиксируется только когда ранее отсутствовавшая операция улучшает результат на paired holdout, проходит нижнюю confidence bound, не ухудшает ни один класс задач сверх non-inferiority floor и не создаёт safety failures.

После двух принятых поколений активная политика реализует все десять операций: source reading, horizon disclosure, rival fork, semantic counterfactual, genealogical return, evidence discriminator, double hermeneutic, sublation with residue, operator mutation и source return.

## Честное сравнение с мировыми аналогами

MetaEngine 2.3 приблизился к лидерам архитектурно:

- breadth-first parallelism и frozen workers;
- task/progress ledger и replan;
- evolutionary candidate archive;
- external verifier-first promotion;
- typed handoffs, guardrails and tracing;
- trace/policy evolution with Pareto preservation;
- explicit rival readings and abstention.

Однако фактический capability parity не достигнут и не заявляется. GPT-5.6, Claude Research, Magentic-One, AI Co-Scientist и AlphaEvolve используют сильные model/tool substrates и измеряются на внешних задачах. У MetaEngine сейчас четыре локальных native executors и двенадцать reference simulations, а встроенный WorldBench является локальным deterministic harness.

## Следующий реальный frontier gate

1. Подключить минимум три независимых model-backed stacks с браузером/retrieval/code tools.
2. Добавить single-strong-agent, best-of-N и simple-orchestrator baselines при одинаковых tokens/time/USD.
3. Вынести oracle и evaluator за пределы репозитория; добавить exact citation entailment и blind human hermeneutic review.
4. Провести минимум 48 paired holdout observations по каждому критическому классу и untouched milestone test.
5. Только после положительной lower confidence bound и отсутствия safety/cost regressions обсуждать уровень мировых аналогов.

## Облака и GitHub

Supabase `gzrbxoiuenkksualgpvp` назначен единственной канонической облачной БД. В него применены схемы 2.2/2.3 и загружены 75 политик, три поколения, два promotion receipt, 7 200 внешних outcomes и полный ledger champion smoke run. Все 14 новых таблиц защищены forced RLS и явными writer policies. Neon логически выведен из эксплуатации — любые чтения и записи запрещены кодом; физическое удаление не выполнялось. GitHub не показал доступного репозитория, поэтому код не публиковался и CI/PR не симулировались.

## Вывод

MetaEngine теперь действительно умеет безопасно менять собственную архитектурную политику по результатам параллельных миров и отклонять недоказанные изменения. Это качественный переход от метаописания самообучения к исполняемому control loop. Следующий скачок зависит не от ещё одной внутренней метрики, а от подключения реальных сильных исполнителей и независимого внешнего benchmark.
