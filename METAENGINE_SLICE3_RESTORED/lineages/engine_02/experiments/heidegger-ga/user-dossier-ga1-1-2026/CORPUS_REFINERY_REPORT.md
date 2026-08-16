# Corpus Refinery 0.2.4 — отчёт по нормализации GA-досье

Дата: 11 августа 2026 года  
Движок: `0.2.4-alpha.1`  
Источник: `HGA-USER-DOSSIER-GA01-REALITAET-2026`  
SHA-256 DOCX: `10a338bedb0e9b13a7fba21d04e27e1762e33e7d02e9028c6f6f99e1bfd69453`

## Итог

Этап Corpus Refinery завершён технически и намеренно не завершён семантически.

Движок теперь умеет разбирать составной DOCX не как единый авторский текст, а как сохраняемый корпус с несколькими конкурирующими разметками. Он отделяет кандидатов на источник, реконструкцию, тезис проекта, возражение и tool/protocol residue, но не присваивает им окончательное авторство. История не удаляется, A/P/B не выдумываются, а canonical argument остаётся `SUSPEND` до разрешения источников и ручной аттестации.

Результат полного запуска: все схемы прошли, удалено 0 сегментов, дословных утечек длинных исходных абзацев не обнаружено.

## 1. Что реализовано

Новая команда:

```bash
node ./bin/destruktion.mjs refine-docx source.docx \
  --job docx_job.json \
  --page-run existing-analyze-docx-output \
  --out refinery-output
```

Если `--page-run` не указан, создаётся свежий transient render. При переиспользовании старого запуска нормализатор проверяет SHA-256 и размер DOCX, source ID, source admission, manifest и запрет expressive text.

Выходы:

| Артефакт | Назначение |
|---|---|
| `segmentation_manifest.json` | OOXML-, renderer- и argument-native units с selectors, hashes и feature codes |
| `source_map.json` | catalog aliases, GA volume locators и hashed unresolved pseudo-citations |
| `claim_ledger.jsonl` | очередь тезисов-кандидатов с origin, type, scale, RT, revision condition и history |
| `hypothesis_bank.json` | тематические lexical clusters и seven-case test matrix |
| `archive_map.json` | exact/near duplicate links и tool-log archive без удаления |
| `formula_registry.json` | отдельная фиксация OMML containers без текста формул |
| `canonical_argument.md` | безопасный scaffold; не автоматическая философская синтезация |

## 2. Три конкурирующие сегментации

| Сегментация | Единиц | Авторитет |
|---|---:|---|
| OOXML-native | 33 870 | порядок paragraphs в `word/document.xml`; heading path и paragraph selector |
| Renderer-native | 13 242 | технические R0001–R0697; не GA и не авторская пагинация |
| Argument-native | 10 569 | bounded windows одного heading path/layer, максимум 6 paragraphs или 2 000 знаков |

Ни одна разметка не объявлена философски правильной. Эмпирическая фаза должна сравнить их на одной выборке, а не выбрать одну постфактум по удобному результату.

## 3. Маршрутизация слоёв

| Candidate layer | OOXML paragraphs | Доля |
|---|---:|---:|
| `UNRESOLVED` | 32 551 | 96,11% |
| `SOURCE` | 810 | 2,39% |
| `RECONSTRUCTION` | 160 | 0,47% |
| `RIVAL_OBJECTION` | 140 | 0,41% |
| `PROTOCOL_TOOL_LOG` | 105 | 0,31% |
| `PROJECT_CLAIM` | 104 | 0,31% |

Высокая доля `UNRESOLVED` — не дефект recall, а защита от ложного авторства. `SOURCE` означает только наличие quote/style/language/citation/locator signals. Он не доказывает, что passage — цитата, что она точна или что найден первичный источник.

## 4. Claim ledger

Создано 2 387 записей из 10 569 argument windows.

| Claim type | Число |
|---|---:|
| `UNRESOLVED_ASSERTION` | 805 |
| `SOURCE_PASSAGE` | 609 |
| `QUESTION` | 433 |
| `CONCLUSION` | 149 |
| `RECONSTRUCTION` | 143 |
| `OBJECTION` | 107 |
| `PROJECT_ASSERTION` | 84 |
| `PROTOCOL_ACTIVITY` | 57 |

Масштабные кандидаты: 1 900 local, 295 work-level, 96 diachronic, 85 universal и 11 epochal. Эти числа являются размером очереди риска, а не количеством истинных тезисов данного масштаба.

У всех 2 387 записей:

- `A = null`, `P = null`, `B = null`;
- `operative_relation_status = UNADJUDICATED`;
- `strongest_rival = null`;
- `human_attested = false`;
- заполнено условие пересмотра и событие decision history.

Это блокирует наиболее опасную форму автоматизации: правдоподобную реконструкцию аргумента без источникового контроля.

## 5. Source map

| Показатель | Результат |
|---|---:|
| Catalog-alias targets | 4 |
| GA-volume candidates | 51 том |
| GA-locator occurrences | 495 |
| Pseudo-citation occurrences | 336 |
| Pseudo-citation hash clusters | 44 |
| OOXML hyperlinks | 0 |
| Claim-level resolved citations | 0 |

Catalog aliases обнаружили `HGA-PJ25-1912-REALITAET`, Klostermann Editionsplan, *Becoming Heidegger* и Glazebrook. Они остаются lexical candidates: совпадение имени или заглавия не разрешает конкретный тезис к странице и изданию.

Gate source resolution: `SUSPEND`.

## 6. Дубликаты и история

| Показатель | Результат |
|---|---:|
| Exact duplicate groups | 46 |
| Дополнительные exact occurrences | 71 |
| Near-duplicate groups при 3-token MinHash/Jaccard ≥ 0,72 | 0 |
| Архивированные tool/log paragraphs | 53 |
| Удалённые paragraphs | 0 |

Первое вхождение exact group становится representative, остальные получают обратимую архивную ссылку. Near duplicates не удаляются даже при совпадении: это только review-link.

Ноль high-overlap near groups не означает отсутствия семантически близких итераций. Он означает, что автоматический lexical criterion не получил права их объединить. Семантическую схожесть нельзя подменять снижением порога до появления удобных кластеров.

## 7. OMML

DOCX содержит 3 908 `m:t` runs, организованных в 1 139 OMML containers. Отдельный registry зафиксировал:

- 216 subscript structures;
- 1 superscript structure;
- 44 exact formula groups и 129 дополнительных formula occurrences;
- hashes OMML и нормализованного видимого содержания;
- 0 выпущенных текстов формул.

Это устраняет смешение математических объектов с короткими обычными paragraphs, но не интерпретирует формулы математически.

## 8. Hypothesis bank

Минимальный lexical threshold прошли восемь кластеров:

1. реальность и реализм;
2. акт, содержание и предмет;
3. региональный профиль реализации;
4. диахронический Хайдеггер;
5. realitas — Wirklichkeit — Existenz — Sein;
6. самоприменение критики;
7. техника и ordering;
8. индивидуация и идентичность.

Семичленная матрица полностью представлена: камень, организм, боль, деньги, технический артефакт, математический и фикциональный объект.

Статус всех элементов: `ELIGIBLE_FOR_HUMAN_REVIEW` или `ELIGIBLE_FOR_HETEROGENEOUS_STRESS_TEST`. Lexical coverage показывает, где ставить вопрос, но не подтверждает модель.

## 9. Privacy и reproducibility

Проверены 1 210 исходных paragraphs длиной от 80 символов и минимум 12 слов. Ни один не найден дословно в производных JSON/Markdown.

Дополнительно установлено:

- `_text` отсутствует в output;
- `raw_text_included = false`;
- `expressive_context_included = false`;
- DOCX, PDF и extracted text не копируются;
- каждый OOXML paragraph имеет `OoxmlParagraphSelector` с part, ordinal и normalized SHA-256;
- старый renderer-run связан с тем же DOCX SHA-256.

## 10. Проверка реализации

- 6 новых JSON Schemas;
- 38/38 автоматических тестов;
- отдельный end-to-end DOCX fixture;
- mutation test блокирует несовпадающий DOCX/page-run hash;
- все 2 387 JSONL entries прошли свою схему;
- 0 schema errors на полном досье;
- frozen CORE 4.0.0-alpha.1 не изменён.

## 11. Что Corpus Refinery не решил

- не установил авторство candidate layers;
- не разрешил claim-level citations;
- не построил A/P/B;
- не выбрал strongest rivals;
- не измерил precision/recall;
- не создал semantic gold;
- не подтвердил диахроническую траекторию;
- не превратил семь случаев в benchmark;
- не сформировал canonical philosophical argument.

Именно поэтому `canonical_argument.md` имеет статус `SUSPENDED_PENDING_SOURCE_RESOLUTION_AND_HUMAN_ADJUDICATION`.

## 12. Следующий обязательный gate — 0.3

Следующий этап должен быть не расширением онтологии, а измерением качества:

1. заморозить стратифицированную выборку ledger candidates и non-candidate argument windows;
2. привлечь минимум двух независимых RU/DE-кодировщиков;
3. кодировать origin layer, claim type, scale, A/P/B, operative/mentioned relation, RT, source resolution и strongest rival;
4. до adjudication вычислить confusion matrices, precision/recall/F1 и Krippendorff α;
5. сравнить lexical baseline, Corpus Refinery routing и сильный hybrid comparator;
6. отдельно прогнать следующую работу GA 1 — *Neuere Forschungen über Logik* — и seven-case pilot;
7. сохранить отрицательные результаты и сократить правила, которые не выдержат абляцию.

## Вердикт

DAE 0.2.4 решает структурную задачу: делает составное досье адресуемым, неразрушающим и пригодным для независимой проверки. Он не решает содержательную задачу за эксперта — и это является правильным результатом данного этапа.
