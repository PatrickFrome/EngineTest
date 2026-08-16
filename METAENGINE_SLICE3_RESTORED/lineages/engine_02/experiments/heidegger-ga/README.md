# Heidegger GA pilot

Воспроизводимый пилот DAE на каталоге Gesamtausgabe, GA 1, p. 1 и полной первой работе 1912 года.

## Артефакты

- `catalog_snapshot.json` — 105 записей официального Editionsplan, библиографический claim ceiling;
- `protocols/` — локальный PASS, source REVIEW и два ожидаемых SUSPEND;
- `research_plan.json` + lock — замороженный корпусный план с заблокированным исполнением;
- `synthetic-german-smoke.md` и `generated/` — безопасный regression fixture немецкого analyzer;
- `RESULTS.json` — машиночитаемый итог;
- `PILOT_REPORT.md` — интерпретация результатов и следующий маршрут.
- `full-work-1912/` — source manifest, безопасный page-aware output, аргументный граф, абляции, пять protocol runs и глубокий отчёт всей работы.
- `user-dossier-ga1-1-2026/` — отдельный DOCX stress test: 697 renderer pages, Unicode-ablation, 840 review records и quarantine verdict; он не смешан с первичным текстом 1912 года.

## Повторение

```bash
npm run build:ga-catalog
npm run pilot:ga1-work -- --out ./ga1-work-derived
node ./bin/destruktion.mjs validate-argument ./experiments/heidegger-ga/full-work-1912/argument_graph.json
node ./bin/destruktion.mjs protocol-run ./experiments/heidegger-ga/protocols/ga01-local-claim-pass.json
node ./bin/destruktion.mjs protocol-run ./experiments/heidegger-ga/protocols/catalog-source-audit-review.json
node ./bin/destruktion.mjs protocol-run ./experiments/heidegger-ga/protocols/development-claim-suspend.json
node ./bin/destruktion.mjs protocol-run ./experiments/heidegger-ga/protocols/reale-translation-suspend.json
node ./bin/destruktion.mjs verify-plan ./experiments/heidegger-ga/research_plan.json ./experiments/heidegger-ga/research_plan.lock.json
```

Команды `SUSPEND` намеренно возвращают exit code 1: это CI-блокировка, а не runtime failure.
