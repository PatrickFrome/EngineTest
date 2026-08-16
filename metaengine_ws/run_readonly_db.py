#!/usr/bin/env python3
"""METAENGINE — run the read-only federation shadow store end-to-end.

Starts the local federation shadow store server (HTTP JSON-RPC + SQLite),
seeds it from the bundled ``LIVE_CANONICAL_READBACK.json``, wires the real
:class:`SupabaseCanonicalAdapter` (``read_only=True``) to it via
:class:`NetworkedFederationTransport`, and executes the read-only canonical
queries through the adapter. Finally verifies the live shadow-store values
match the canonical anchors (cp001 / active_policy 1868b3c7... / gen 2).

This is a genuinely executing read-only DB. It is explicitly labelled
``LOCAL_FEDERATION_SHADOW_STORE`` (NOT the canonical Supabase authority;
those credentials are absent from the recovery capsule — see KNOWN_LOSSES).

Usage::

    python3 run_readonly_db.py
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = 5433
DB = ROOT / "var" / "federation_store.db"
SEED = ROOT / "03_EVIDENCE" / "METAENGINE1" / "current_canonical_readback.json"

EXPECTED_CHECKPOINT_ID = "metaengine-chat-2.3.0-alpha.1-cp001"
EXPECTED_ACTIVE_POLICY_HASH = (
    "1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48"
)
EXPECTED_CHAMPION_GENERATION = 2


def _wait_for_port(port: int, timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), 0.5):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def main() -> int:
    DB.parent.mkdir(parents=True, exist_ok=True)
    if not SEED.is_file():
        print(f"FAIL: seed readback not found at {SEED}", file=sys.stderr)
        return 2

    # 1. Start the shadow store server in the background.
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "metaengine.federation_store.server",
            "--port",
            str(PORT),
            "--host",
            "127.0.0.1",
            "--db",
            str(DB),
            "--seed",
            str(SEED),
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        if not _wait_for_port(PORT):
            out = proc.stdout.read() if proc.stdout else ""
            print("FAIL: server did not start in time.", file=sys.stderr)
            print(out, file=sys.stderr)
            return 1
        startup_line = proc.stdout.readline() if proc.stdout else ""
        print("=== server started ===")
        print(startup_line.rstrip())

        # 2. Wire the real adapter (read_only=True) to the shadow store.
        from metaengine.devfabric.providers.supabase import SupabaseCanonicalAdapter
        from metaengine.federation_store.transport import NetworkedFederationTransport

        transport = NetworkedFederationTransport(f"http://127.0.0.1:{PORT}")
        adapter = SupabaseCanonicalAdapter(transport, read_only=True)

        print("\n=== read_store_manifest (through transport) ===")
        manifest = transport.read_store_manifest()
        print(json.dumps(manifest, indent=2, default=str))

        print("\n=== adapter.read_current_checkpoint() ===")
        checkpoint = adapter.read_current_checkpoint()
        print(json.dumps(checkpoint, indent=2, default=str))

        print("\n=== adapter.read_champion() ===")
        champion = adapter.read_champion()
        print(json.dumps(champion, indent=2, default=str))

        # 3. Verify anchors match canonical expectations.
        print("\n=== anchor verification ===")
        findings = []
        if checkpoint.get("checkpoint_id") != EXPECTED_CHECKPOINT_ID:
            findings.append(f"checkpoint_id mismatch: {checkpoint.get('checkpoint_id')!r}")
        if checkpoint.get("active_policy_hash") != EXPECTED_ACTIVE_POLICY_HASH:
            findings.append("active_policy_hash mismatch")
        if checkpoint.get("verification_status") != "VERIFIED":
            findings.append(f"not VERIFIED: {checkpoint.get('verification_status')!r}")
        if not checkpoint.get("is_current"):
            findings.append("not current")
        if champion.get("policy_hash") != EXPECTED_ACTIVE_POLICY_HASH:
            findings.append("champion policy_hash mismatch")
        if int(champion.get("generation", -1)) != EXPECTED_CHAMPION_GENERATION:
            findings.append(f"champion gen mismatch: {champion.get('generation')!r}")

        if findings:
            print("ANCHOR_VERIFY_FAIL:")
            for f in findings:
                print("  -", f)
            return 1

        print("ANCHOR_VERIFY_PASS: cp001 / active_policy 1868b3c7... / champion gen 2")
        print(f"  store_kind          = {manifest.get('store_kind')}")
        print(f"  canonical_authority = {manifest.get('canonical_authority')}")
        print(f"  seeded_from         = {manifest.get('seeded_from','')[:60]}...")
        print(f"  dev_receipt_count   = {manifest.get('development_receipt_count')}")

        # 4. Prove mutation is fail-closed even through the adapter.
        print("\n=== mutation fail-closed proof ===")
        from metaengine.devfabric.providers.external import ConnectorPolicyError

        try:
            adapter.append_development_receipt({"x": 1}, write_intent="APPEND_RECEIPT")
            print("FAIL: mutation unexpectedly succeeded")
            return 1
        except ConnectorPolicyError as exc:
            print(f"append_development_receipt -> ConnectorPolicyError({exc.reason_code}) [expected]")
        try:
            adapter.propose_checkpoint({"x": 1}, expected_parent="cp001", write_intent="PROPOSE_CHECKPOINT")
            print("FAIL: mutation unexpectedly succeeded")
            return 1
        except ConnectorPolicyError as exc:
            print(f"propose_checkpoint       -> ConnectorPolicyError({exc.reason_code}) [expected]")

        print("\nREADONLY_DB_PASS")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
