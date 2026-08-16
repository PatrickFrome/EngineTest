# Пользовательское досье GA 1.1 — DOCX-прогон

Этот эксперимент обрабатывает пользовательский DOCX как составное исследовательское досье, а не как текст GA 1.1. Исходный файл не включён в проект. Зафиксированы его SHA-256, OOXML-структура, производная техническая пагинация и review-only результаты.

`run/` содержит текущий прогон после исправления Unicode-границ. `run-before-unicode-fix/` сохранён как отрицательная абляция: он демонстрирует, почему ASCII `\b` непригодна для русскоязычного корпуса.

`refinery/` содержит этап 0.2.4: три конкурирующие сегментации, неэкспрессивную карту источников, claim ledger, банк гипотез, отдельный OMML-реестр и неразрушающую архивную карту. Нормализатор не создаёт «канонический аргумент» сам: соответствующий файл является scaffold со статусом `SUSPENDED_PENDING_SOURCE_RESOLUTION_AND_HUMAN_ADJUDICATION`.

`expert-cycle-0.5/` содержит арбитражный режим 0.5: обязательный ETY-0.2 pre-pass, предметный профиль, три аналитических прохода и синтез. В отличие от refinery review queue, цикл обязан завершить каждый тезис; нехватка evidence фиксируется терминальным `INSUFFICIENT`. Главный выход — `expert-cycle-0.5/FINAL_ANALYTICS.md`, канонический machine artifact — `expert-cycle-0.5/expert_cycle.json`.

`living-analysis-0.5/` содержит неарбитражный D3-EXPLORATORY: восемь констелляций, нелинейный граф, межтемные переходы, обязательные ETY-карточки и первичную `PHILOSOPHICAL_FIELD_NOTE.md`. Этот слой сознательно не использует terminal verdict, confidence или true/false; его остановка означает достаточную открытость и наличие условия повторного открытия.

Главные документы:

- `DOSSIER_RUN_REPORT.md` — интерпретация и решения;
- `CONTENT_ASSESSMENT.json` — структурированная оценка ценности и допустимости;
- `CORPUS_REFINERY_ASSESSMENT.json` — оценка нормализации 0.2.4 и её границ;
- `expert-cycle-0.5/FINAL_ANALYTICS.md` и `.json` — финальный арбитражный вывод текущего прогона;
- `expert-cycle-0.5/expert_trace.json` — этимологический предпроход, реконструктор, критик, арбитр, gates и provenance без исходного текста;
- `living-analysis-0.5/PHILOSOPHICAL_FIELD_NOTE.md` — первичная живая аналитика через межконстелляционные маршруты;
- `living-analysis-0.5/living_analysis.json` и `operator_trace.json` — проверяемый граф и происхождение каждого шага;
- `living-analysis-0.5/etymology_pass.json` и `ETYMOLOGICAL_ANALYSIS.md` — обязательный ETY-0.2;
- `RESULTS.json` — основные метрики;
- `ABLATION_RESULTS.json` — до/после Unicode-fix;
- `protocols/` — пять protocol runs;
- `run/docx_intake.json` — фиксация DOCX, рендера и document hygiene;
- `run/generated/analysis_bundle.json` — page-resolved производный bundle без полного текста.
- `refinery/segmentation_manifest.json` — OOXML-, renderer- и argument-native единицы без исходных формулировок;
- `refinery/claim_ledger.jsonl` — 2 387 неаттестованных тезисов-кандидатов с пустыми A/P/B;
- `refinery/source_map.json`, `hypothesis_bank.json`, `archive_map.json`, `formula_registry.json` — источники, вопросы, история и OMML.

Потолок вывода: refinery остаётся очередью кандидатов, а expert cycle — завершённой адъюдикацией этой очереди в пределах текущего evidence/profile. Он не устанавливает непогрешимость, внешнюю валидность или статус файла как первичного источника.
