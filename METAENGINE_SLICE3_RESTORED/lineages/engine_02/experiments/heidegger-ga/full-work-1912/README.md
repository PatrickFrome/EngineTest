# Full-work pilot: *Das Realitätsproblem* (1912)

Производный анализ оригинальной журнальной публикации, *Philosophisches Jahrbuch* 25, с. 353–363, с частичной сверкой GA 1, с. 1–15.

## Артефакты

- `source_manifest.json` — библиография, два SHA-256, пагинация, access policy и crosswalk;
- `generated/` — 24 page-resolved review records и bundle без исходного текста;
- `argument_graph.json` — применимые pro/con аргументы, итог `CONTESTED`;
- `protocols/` — source `REVIEW`, moderate claim `PASS`, ontology/data/ablation `SUSPEND`;
- `ABLATION_RESULTS.json` — legacy/page/notes/modal comparison;
- `RESULTS.json` — машиночитаемый итог;
- `FULL_WORK_REPORT.md` — содержательный разбор.

## Воспроизведение

Требуются Node.js 20+, сеть и Poppler `pdftotext`. PDF и полный текст создаются во временном каталоге, проверяются по hash и удаляются.

```bash
npm run pilot:ga1-work -- --out ./ga1-work-derived
node ./bin/destruktion.mjs validate-argument ./experiments/heidegger-ga/full-work-1912/argument_graph.json
```

Вывод `PASS` относится к conformance и claim discipline, а не к философской истинности.
