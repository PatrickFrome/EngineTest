# Metaengine Stage D — Remote Edge Fabric

This package is a non-canonical Cloudflare edge control plane. It exposes only content-addressed references and metadata-safe operations.

## Authority boundary

- Supabase remains the sole canonical checkpoint/policy authority.
- This Worker cannot promote a candidate, run arbitrary SQL/shell, read secrets, or accept P3 payloads.
- D1 contains only ephemeral leases, task/candidate references, verification requests, and quota snapshots.
- R2 keys are SHA-256 content addresses and uploads bind an expected SHA-256 checksum.
- Workflows store references, not source/patch bodies.
- Workers AI is optional, P0/P1 only, and fails closed when free quota is unknown/exhausted.

## Local gate

`npm install` is required before the Cloudflare SDK transport can be type-checked or previewed. If the npm registry is unavailable, do not fabricate `package-lock.json`; run the dependency-free core tests with Node 22 instead.

No deployment is authorized by Stage D implementation alone.
