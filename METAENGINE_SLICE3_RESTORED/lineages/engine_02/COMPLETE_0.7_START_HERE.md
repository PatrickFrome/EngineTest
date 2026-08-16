# Destruktion 4.0 Complete 0.7 — Start Here

This archive combines the frozen 0.10 open-set engine with Destruktion Studio 0.7 independent-family ecology integration.

## Start

Windows:

```text
SETUP.cmd
START_STUDIO.cmd
```

Direct check:

```text
node studio/studio.mjs doctor
node --test
```

## New 0.7 regression

```text
node studio/studio.mjs ecology:independent experiments/independent-family-ecology-0.10/micro_local_ecology_manifest.json --out ./workspace/independent-ecology
node studio/studio.mjs ecology:downstream ./workspace/independent-ecology/micro_local_ecology_result.json --out ./workspace/independent-downstream
```

For an unseen DOCX:

```text
node studio/studio.mjs family:probe ./source.docx --out ./workspace/family-probe
```

The probe is intentionally non-promoting. Read `ENGINE_INTEGRATION_REPORT_0.7.md` before treating a new family as more than an experimental routing hypothesis.
