# Destruktion 4.0 — Development Report 0.10

## Open-Set Hermeneutic Discovery

Версия `0.10.0-alpha.1` продолжает Genetic–Ecological Merge 0.9. В 0.9 source-forced delta вновь стал исполнимым и мог породить candidate registry; в 0.10 снимается следующий предел: само рождение operator больше не обязано оставаться внутри заранее перечисленных ontological/profile families.

### Главный архитектурный delta

До 0.10 source resistance мог показать, что topic registry слеп, однако затем representation failure всё равно переводился в конечный vocabulary известных отношений. 0.10 вводит отдельный open-set route:

`SOURCE → REGISTRY_BLIND_SPOT → MICRO_LOCAL_WINDOWS → UNKNOWN_OPERATOR_FAMILY → ADD_OPERATOR → CANDIDATE_REGISTRY → LIVING RUNTIME`.

Known-profile route не удалён. Он сохраняется как rival, поэтому open-set discovery не получает привилегии новизны.

### Реализовано

- `src/open-set-discovery.mjs`: source-signature discovery и детерминированный `UNKNOWN_OPERATOR_FAMILY` candidate;
- overlapping micro-local argument windows;
- rival unitizations `TERM_FIELD`, `WINDOW_TRANSITION`, `NEGATIVE_BOUNDARY`;
- `src/micro-local-ecology.mjs` и CLI `micro-local-ecology`;
- schema `micro_local_ecology_result.schema.json`;
- GX7 declarative emission отдельного open-set `OPERATOR_DELTA`;
- mutation kind `ADD_OPERATOR`;
- candidate-registry addition без изменения baseline;
- `REMOVE_ADDED_OPERATOR` rollback;
- full runtime reachability для новых conditional families;
- regression fixture `open-set-add-family.pass.json`;
- три новых evolution tests; ожидаемый полный suite — 80 tests;
- portable manifest расширен open-set runtime, schema и controlled evidence.

### Controlled regression

Использован прежний Descartes cogito negative control. Это важно: новый механизм не должен спасать relation-genesis ценой ложного срабатывания.

Получено:

- source resistance: `REGISTRY_BLIND_SPOT`;
- known relation profile hints: `[]`;
- relation-genesis negative control сохранён;
- open-set status: `OPEN_SET_RIVAL_REQUIRED`;
- candidate: `F-OPEN-THINKING_UNDERSTANDING_EXIST-995658EA1060`;
- source triggers: `thinking`, `understanding`, `exist`, `mind`, `thought`;
- micro-local windows: 5;
- routes: 5 × `OPEN_SET_LOCAL_CANDIDATE`;
- mutation decision: `ACCEPTED_CANDIDATE`;
- runtime reachability: `FULL`;
- mutation gate errors/review/warnings: 0/0/0;
- baseline living graph: 101 nodes / 149 edges / 0 open-family nodes;
- mutant living graph: 104 nodes / 153 edges / 3 open-family nodes.

Это доказывает узкое инженерное утверждение: open-set candidate способен стать реально исполнимым оператором и изменить living graph, не мутируя baseline registry. Это **не** доказывает, что выделенное cogito-family является философски правильной категорией.

### Что стало нелинейнее

0.8: operators конкурировали локально на corpus target.

0.9: source-forced mutation снова могла реально переписать candidate registry.

0.10: система допускает, что сам vocabulary конкурентов недостаточен, и создаёт reversible unknown family на micro-local source field.

Таким образом, нелинейность впервые распространяется не только на traversal и выбор оператора, но и на **пространство допустимых operator families**.

### Главный предел 0.10

Open-set discovery всё ещё строится на lexical recurrence/co-occurrence и source centrality. Он пока не умеет надёжно различать:

- утверждение и отрицание;
- авторскую позицию и цитируемую позицию;
- тезис и условную/контрфактическую формулировку;
- термин как объект критики и термин как собственный аналитический ресурс;
- локальный rhetorical effect и устойчивую conceptual function.

Следовательно, следующий этап не должен добавлять новые families. Он должен атаковать **само подтверждение open-set candidate**.

### Рекомендуемый следующий gate: 0.11

`ADVERSARIAL SEMANTIC ROLE & ANTI-SELF-CONFIRMATION`

Минимальный контракт:

1. predicate/polarity/modality/attribution/argument-role representation;
2. decoy relation/open-set terminology;
3. paraphrase invariance;
4. translation perturbation;
5. negation inversion;
6. quoted-opponent contamination;
7. blinded heterogeneous corpus regression;
8. automatic quarantine when candidate survives only lexical surface form.

Claim ceiling 0.10: `OPEN_SET_OPERATOR_CANDIDATE_NOT_DISCOVERED_ONTOLOGY_OR_CORE_PROMOTION`.
