# Architecture Source Library

This directory contains small tracked source cards, source-pack manifests, verification receipts, mechanism hypotheses, and the deterministic registry index for METAENGINE-1 Slice 3.

Foreign source bytes are never stored here or imported as runtime code. They live in the excluded external vault at `reference-vault/blobs/sha256/<digest>`. The Core verifier performs no network requests.

## Rebuild from local staging

Stage only official files pinned by `catalog/first_wave.json` beneath:

```text
reference-vault/staging/<source_id>/<staged_path>
```

Then run:

```bash
python scripts/architecture_source_registry.py ingest \
  --catalog research/architecture_library/catalog/first_wave.json \
  --staging-root reference-vault/staging \
  --vault-root reference-vault \
  --output-root research/architecture_library
```

Verify without network access:

```bash
python scripts/architecture_source_registry.py verify \
  --registry research/architecture_library/registry.json \
  --vault-root reference-vault
```

A source record reaching `INGESTED` proves only exact-byte retention, provenance classification, and license evidence. It does not prove usefulness, causal transfer, scientific truth, or assimilation. Slice 3 caps every mechanism at A0/A1.
