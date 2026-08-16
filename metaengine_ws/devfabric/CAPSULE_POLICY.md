# Metaengine Development CONTROL Capsule Policy

The CONTROL capsule is the portable chat-development control plane. It deliberately excludes immutable lineage bytes and heavyweight forensic evidence; those remain in the Local FULL vault. `devfabric/LINEAGE_LOCK_SHA256.txt` binds every lineage byte by path and SHA-256.

Excluded from CONTROL: `.git`, `.worktrees`, `.venv`, caches, `lineages/`, `release-evidence/`, `release_evidence/`, runtime journals/worktrees/candidates, `dist/`, `.env*` except `.env.example`, and credential-bearing runtime state.

The capsule contains a generated `devfabric/CAPSULE_MANIFEST.json` with sorted payload rows, file sizes, normalized modes, payload root, source artifact binding, and lineage-lock digest. ZIP timestamps are normalized to 1980-01-01 00:00:00 and member order is lexical.

A CONTROL capsule never grants canonical write authority. Supabase promotion remains a separate guarded operation outside Stage A.

The Stage A gate receipt is an external attestation over the capsule hash and is intentionally excluded from the capsule payload to avoid a self-referential hash cycle.
