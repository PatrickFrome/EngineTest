# D6-F Controlled Multi-Chat Pilot Runbook

## Status boundary

`MULTI_CHAT_UI_STATUS=READY_FOR_CANARY_NOT_OBSERVED` until a human-observed ordinary-chat canary produces valid federation receipts. Machine simulation, Supabase RPC tests, Project memory, or a single conversation must never be relabeled as `PASS_CANARY`.

All chats use the **same CONTROL capsule**. Role-specific archives are forbidden. Project memory is ambient context only; Supabase ledger receipts, Git/CAS references, and fencing generations are machine truth.

## Minimum ordinary-chat canary

The **user opens** four ordinary ChatGPT chats manually and loads the same CONTROL capsule in each:

- **C0 — SYNCHRONIZER_INTEGRATOR**: registration, integration decision, synchronization snapshot, then loss/recreation test.
- **C2 — CORE_ENGINE**: isolated core task and one candidate receipt.
- **C4 — EDGE_MCP**: isolated edge/MCP task and one candidate receipt.
- **C6 — VERIFICATION_SECURITY**: independent review of the designated candidate; C6 must not review its own implementation.

No claim of model blindness is made merely because chats are in the same ChatGPT Project. REDUNDANT blind-group evidence requires protocol-level isolation and must be evaluated separately.

## Operator sequence

1. C0 opens/receives the active epoch reference from the internal synchronizer control plane. Ordinary chats do **not** create epochs or tasks.
2. Generate C0/C2/C4/C6 packets from `connected_role_packets(load_bootstrap(...))` and give each chat only its own packet plus the same CONTROL capsule SHA.
3. Each chat calls `federation_register`; the returned `session_id`, `slot_id`, `epoch_id`, `lease_generation`, and role profile are authoritative only if they match its static packet.
4. The control plane provides each producer an `ASSIGNED_TASK_HASH`. C2/C4 call `task_get` and `task_dependencies`; they work in isolated candidate worlds and submit exactly one content-addressed candidate each.
5. C6 fetches the candidate selected for mandatory review and submits an independent PASS/FAIL review receipt. It does not receive canonical promotion authority.
6. C0 reads status, proposes an integration decision only for eligible non-conflicting candidates, and publishes a synchronization snapshot.
7. Record the snapshot hash and integration order outside C0 conversation prose.
8. Destroy/abandon the first C0 chat. The **user opens** a replacement C0 chat, loads the same CONTROL capsule, registers at the next fencing generation, and reconstructs the snapshot from ledger state only.
9. The replacement C0 must reproduce the same snapshot hash/integration order. A late result from the superseded C0 generation must be rejected or stored as `STALE_FENCED` according to the lease protocol.

## PASS criteria

The UI canary may change status to `MULTI_CHAT_UI_STATUS=PASS_CANARY` only when all are observed:

- unique valid registrations for C0/C2/C4/C6;
- two isolated producer tasks, one valid candidate from C2 and one from C4;
- required C6 independent review accepted;
- C0 synchronization snapshot accepted and content-addressed;
- first C0 is replaced/reclaimed and the old generation is fenced;
- replacement C0 reproduces state without access to prior C0 conversation prose;
- canonical checkpoint/champion/policy are unchanged by the canary.

Until then the only truthful UI status is `READY_FOR_CANARY_NOT_OBSERVED`.

## Immutable finalization lifecycle (D6-G0)

After a real ordinary-chat canary has reached `PASS_CANARY_MANUAL_RELAY`, the terminal lifecycle is:

`PASS_CANARY_MANUAL_RELAY -> FINALIZE -> CLOSED -> release witnesses -> frozen-cut recovery`

`PASS_CANARY_MANUAL_RELAY is not PASS_MCP_CANARY`. Manual relay proves ordinary-chat federation semantics only; it does not prove a deployed external Federation MCP transport.

The internal C0 control plane finalizes an epoch with protocol `D6.FINALIZATION.1`. The authoritative CLOSED recovery source is `IMMUTABLE_RECOVERY_CUT`. Finalization must content-address the terminal snapshot and recovery cut, close the epoch atomically, and release/fence epoch witnesses. Once CLOSED, historical recovery must use the immutable cut rather than mutable active-session state.

Only a verified `CLOSED` epoch is eligible as an adaptation input. Finalization is internal and is not a chat-facing MCP tool. It must not perform checkpoint, champion, or architecture-policy promotion.
