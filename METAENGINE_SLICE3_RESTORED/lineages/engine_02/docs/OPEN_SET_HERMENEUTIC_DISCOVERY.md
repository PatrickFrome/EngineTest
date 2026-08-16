# OPEN-SET HERMENEUTIC DISCOVERY 0.10

## Назначение

Этот слой расширяет `SOURCE-RESISTANCE / OPERATOR-MUTATION`: source-backed blind spot больше не обязан быть немедленно переведён в уже известный словарь операторов (`difference`, `dependence`, `reciprocity`, `relation-first` и т. п.). Если центральное поле источника устойчиво присутствует в локальных окнах, но не получает достаточного known-profile resolution, система может удержать отдельного соперника `UNKNOWN_OPERATOR_FAMILY`.

Это **не открытие новой онтологии**. Open-set candidate означает только: текущая операторная типология недостаточна для данного source-signature, а потому допустима экспериментальная unitization, которую надо попытаться сделать исполнимой, проверить и при необходимости удалить.

## Инварианты

1. `UNKNOWN_OPERATOR_FAMILY != DISCOVERED_ONTOLOGY`.
2. Open-set candidate не промотируется в CORE автоматически.
3. Явный PROJECT_CLAIM не является достаточным триггером рождения operator family.
4. Source-backed registry blindness обязателен.
5. Known profile, если он существует, не уничтожается open-set candidate: они остаются соперниками.
6. Новый operator обязан иметь source signature, rival unitizations, rollback и retirement condition.
7. Open-set novelty без повторяемого distinction gain является основанием для retirement, а не преимуществом.
8. Маршрутизация выполняется на micro-local windows; whole-corpus synthesis не имеет приоритета.
9. `ABSTAIN_LOCAL` остаётся допустимым результатом.
10. Любой вывод ограничен claim ceiling `OPEN_SET_OPERATOR_CANDIDATE_NOT_DISCOVERED_ONTOLOGY_OR_CORE_PROMOTION`.

## Micro-local source signature

`open-set-discovery.mjs` строит перекрывающиеся argument windows из source-backed сегментов. Для каждого окна сохраняются только прослеживаемые selectors, центральные термины, co-occurrence signatures и known-profile hints; raw source text не включается в portable artifact.

Open-set pressure возникает, когда source-central field повторяется локально, но существующий vocabulary не даёт достаточного разрешения. Candidate получает детерминированный ID вида:

`F-OPEN-<SOURCE-TERMS>-<HASH>`

и минимум три несовместимые unitization hypotheses:

- `U-TERM-FIELD` — сначала читать локальное сосуществование source-native terms, не приписывая им заранее relation ontology;
- `U-WINDOW-TRANSITION` — считать изменение режима между соседними окнами первичным событием анализа;
- `U-NEGATIVE-BOUNDARY` — исследовать разрывы co-occurrence как provisional boundary, не превращая отсутствие в метафизическую сущность.

## Исполнимое рождение operator family

Mutation engine `DAE-OPERATOR-MUTATION-1.3` поддерживает `ADD_OPERATOR`.

Путь:

`REGISTRY_BLIND_SPOT`
→ `UNKNOWN_OPERATOR_FAMILY`
→ `OPERATOR_DELTA(kind=ADD_OPERATOR)`
→ structural/semantic gate
→ same-source executable probe
→ candidate registry
→ runtime execution
→ regression / competition / retirement.

`ADD_OPERATOR` никогда не редактирует baseline registry. Candidate записывается в отдельный registry; rollback для такого delta означает удаление добавленного operator. Runtime reachability должна быть `FULL`, иначе promotion gate не пройден.

## Micro-local ecology

Команда:

```bash
node ./bin/destruktion.mjs micro-local-ecology ./refinery/hypothesis_bank.json --out ./micro-local-output
```

допускает четыре локальных решения:

- `KNOWN_PROFILE_LOCAL`;
- `OPEN_SET_LOCAL_CANDIDATE`;
- `KEEP_KNOWN_AND_OPEN_SET_RIVALS`;
- `ABSTAIN_LOCAL`.

Это routing heuristic, а не truth adjudication. Разные окна одного корпуса могут находиться в разных режимах и менять route на границах argument field.

## Controlled 0.10 regression: Descartes cogito

В controlled dossier Descartes relation-genesis остаётся отрицательным контролем: known relation profile hints отсутствуют. Одновременно source resistance фиксирует центральное поле `thinking / understanding / exist / mind / thought` и создаёт open-set candidate `F-OPEN-THINKING_UNDERSTANDING_EXIST-995658EA1060`.

Пять micro-local windows получают `OPEN_SET_LOCAL_CANDIDATE`. `ADD_OPERATOR` создаёт conditional family в candidate registry; executable probe меняется с `__ABSENT__ / inactive` на новый active operator и mutation gate возвращает `ACCEPTED_CANDIDATE`, `runtime_reachability=FULL`.

Baseline living run: 3 constellations, 101 nodes, 149 edges, 0 узлов нового F-OPEN operator.

Mutant living run: 3 constellations, 104 nodes, 153 edges, 3 узла нового F-OPEN operator.

Следовательно, 0.10 проверяет не только сериализацию candidate metadata: новый family реально меняет runtime graph.

## Самокритика

Open-set discovery пока остаётся source-signature heuristic. Повторяемость слов и co-occurrence ещё не различают отрицание, цитирование чужой позиции, модальность, аргументативную функцию или иронию. Поэтому 0.10 может производить novelty inflation там, где нужен более богатый predicate/attribution analysis.

Следующий gate должен быть adversarial: `span → predicate → polarity → modality → attribution → argumentative role`, плюс paraphrase/translation/decoy tests и heterogeneous corpora. До прохождения такого gate open-set families остаются experimental и reversible.
