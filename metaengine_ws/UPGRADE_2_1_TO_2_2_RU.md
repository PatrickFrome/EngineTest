# Обновление MetaEngine 2.1 → 2.2

## Вариант A: полный portable runtime

Распакуйте полный архив 2.2 в новый каталог. Не накладывайте его поверх работающего 2.1: сохраните старый runtime и его `runs/` до внешнего A/B.

## Вариант B: architecture delta

Delta-пакет содержит изменяемый слой MetaEngine без 9 839 immutable lineage-файлов. Наложите его на чистый runtime 2.1, сохранив структуру каталогов, затем выполните:

```bash
python -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest
python -m metaengine.cli frontier-patterns
python -m metaengine.cli run examples/sample_input.md --out runs/2.2-smoke
```

На Windows используйте `.venv\Scripts\python` и `.venv\Scripts\pytest`.

## База данных

Миграция `storage/frontier_evidence_control_2_2.sql` создаёт пять новых ledger-таблиц. Она подготовлена, но не применялась к live Neon или Supabase в рамках этой интеграции.

Порядок безопасного ввода:

1. применить SQL в изолированной branch/database;
2. выполнить smoke-run и `replicate` только в тестовую цель;
3. проверить 17 frontier insert/upsert statements и RLS;
4. пройти schema drift check;
5. применить в production maintenance window;
6. не включать клиентские policies до выделения отдельной API-схемы.

## Обратимость

2.2 не меняет lineage-файлы. Rollback runtime выполняется возвратом на каталог 2.1. Новые таблицы не удаляйте при rollback: они содержат provenance; достаточно прекратить запись 2.2.
