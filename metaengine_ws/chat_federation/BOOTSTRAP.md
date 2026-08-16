# Metaengine Federated Chat Bootstrap D6.1

## ONE COMMON CONTROL CAPSULE

Every federation slot C0–C7 boots from the same CONTROL capsule. A role-specific archive is forbidden because it would create configuration drift between chats.

The capsule contains only static protocol files, the role catalogue, versioned Role Genomes, source binding, and verification material. Runtime session state, lease generations, credentials, and connector state remain outside the capsule.

## PROJECT MEMORY IS NOT MACHINE TRUTH

ChatGPT Project memory may help a chat understand terminology and nearby conversation history, but it is ambient context only. Assignment, epoch, lease generation, role profile, task identity, candidate state, and integration state must be obtained from the federation protocol or from an explicitly pinned offline packet.

## Bootstrap modes

### CONNECTED

A connected bootstrap verifies the static capsule, then obtains an authoritative registration from the federation control plane. The returned session, epoch, slot, generation, and role profile must agree with local static artifacts before the chat may submit a candidate.

### FROZEN_OFFLINE

Offline mode may activate a static Role Genome and may expose an already-pinned FederatedTaskEnvelope. It must not invent a session id, epoch id, task assignment, lease generation, or authoritative federation state. New authoritative work waits for reconnection.

## Correctness boundary

Chat liveness is not a correctness signal. Replacement is protected by monotonic fencing generations. A late result from a superseded generation remains auditable but is `STALE_FENCED`.

C0 is disposable. It reconstructs synchronization state from the ledger and content-addressed receipts rather than from conversation memory.
