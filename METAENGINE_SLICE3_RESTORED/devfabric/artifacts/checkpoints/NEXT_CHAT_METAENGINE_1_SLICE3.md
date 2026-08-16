# MetaEngine-1 Slice 3 — frozen Task 4 handoff

Status: `FROZEN_WIP_RED`. Development was stopped at the user's request before Task 4 completion.

The repository contains five ingested permissive sources, two registered restricted references, three closed behavioral-only references, 13 verified blob descriptors, and 150,521 logical source bytes. The external reference vault is carried beside CONTROL in the full checkpoint capsule.

The one deliberate RED boundary is:

`tests/test_architecture_source_registry_artifacts.py::test_retrieval_evidence_binds_upstream_git_blobs_to_retained_sha256`

It fails because `research/architecture_library/retrieval_evidence.json` has not yet been materialized. Do not fix anything else before reproducing that exact boundary.

Resume sequence:

1. Verify the outer checkpoint manifest, nested CONTROL capsule, Git bundle, SQLite journal chain, and reference vault.
2. Restore the checkpoint branch/commit recorded by the outer manifest and confirm a clean worktree.
3. Reproduce the recorded RED test.
4. Generate `retrieval_evidence.json` from the 13 staged official files while recomputing every Git blob id and SHA-256.
5. Run the complete Task 4 suite and create a Development Evolution Review receipt before Task 5.

No canonical cloud write, checkpoint promotion, or mechanism assimilation was performed. The next qualitative leap after Task 4 is signed provenance plus independent mirrors, followed by evidence-scored mechanism tournaments.
