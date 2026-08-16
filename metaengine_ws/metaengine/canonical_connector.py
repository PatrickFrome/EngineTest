"""METAENGINE — safe READ-ONLY canonical Supabase connector.

Wires the existing :class:`metaengine.devfabric.providers.supabase.SupabaseCanonicalAdapter`
(read_only=True) to the REAL canonical Supabase/Postgres store identified in
``config/CANONICAL_SUPABASE.json`` (project ``gzrbxoiuenkksualgpvp``).

This is the "freshly read" live canonical query that constitutional boundary 2
explicitly permits: "Supabase/PostgreSQL is the sole mutable canonical authority
only when actually connected and freshly read."

Safety design (honours boundaries 3, 6, 7):

* **Read-only.** Pure SELECTs only (the ``canonical_readback.sql`` queries).
  The bundled ``metaengine_db_admin.verify()`` does a DDL probe
  (create/insert/update/delete/drop table in ``destruktion_meta``) inside a
  savepoint+rollback — we deliberately OMIT that probe so the canonical schema
  is never touched, even rolled back.
* **Fail-closed on mutation.** ``read_only=True`` makes
  :meth:`SupabaseCanonicalAdapter.append_development_receipt` /
  :meth:`propose_checkpoint` raise ``ConnectorPolicyError``. There is no
  ``exec-sql`` / ``restore`` path here. Canonical mutation requires a
  SEPARATELY AUTHORIZED GATE (boundary 3).
* **No secrets in code/git.** ``METAENGINE_DATABASE_URL`` is read from the
  environment only; never logged, never persisted. (boundary 6)
* **Anchor verification.** After connecting, :meth:`verify_against_expected`
  confirms the live checkpoint/champion match the canonical anchors
  (cp001 / active_policy ``1868b3c7...`` / champion gen 2). A mismatch raises
  ``CanonicalAnchorMismatch`` and refuses to proceed.

Usage (read-only verify)::

    METAENGINE_DATABASE_URL='postgresql://...' \\
        python3 -m metaengine.canonical_connector verify

The connection string must be injected via the trusted runtime environment
(reacquire from Supabase Dashboard -> Connect). Do not paste it into chat or
commit it to the project.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

try:
    import psycopg  # psycopg v3
except ImportError as exc:  # pragma: no cover
    psycopg = None  # type: ignore[assignment]


PROJECT_REF = "gzrbxoiuenkksualgpvp"
EXPECTED_CHECKPOINT_ID = "metaengine-chat-2.3.0-alpha.1-cp001"
EXPECTED_ACTIVE_POLICY_HASH = (
    "1868b3c7d93536cddfc1db842b0cc60b04e2822acdef65933e8bfe724df8ae48"
)
EXPECTED_CHAMPION_GENERATION = 2


class CanonicalConnectorError(RuntimeError):
    """Base error for canonical connector failures."""


class CredentialsMissing(CanonicalConnectorError):
    pass


class CanonicalAnchorMismatch(CanonicalConnectorError):
    pass


# ---------------------------------------------------------------------------
# Read-only transport implementing SupabaseTransport (pure SELECTs)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CanonicalReadback:
    checkpoint: dict[str, Any]
    champion: dict[str, Any]
    identity: dict[str, Any]
    source: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "checkpoint": self.checkpoint,
            "champion": self.champion,
            "identity": self.identity,
            "source": self.source,
        }


class ReadOnlyCanonicalTransport:
    """A :class:`SupabaseTransport` backed by the real canonical Postgres.

    Only the two read methods (``read_current_checkpoint``, ``read_champion``)
    are implemented as live SELECTs. The mutation methods
    (``append_development_receipt``, ``propose_checkpoint``) raise
    ``ConnectorPolicyError`` unconditionally — this transport is read-only by
    construction, independent of the adapter's ``read_only`` flag.
    """

    connector_id = "canonical-supabase-read-only"
    store_kind = "CANONICAL_SUPABASE_LIVE"

    def __init__(self, database_url: str):
        if psycopg is None:
            raise CanonicalConnectorError(
                "psycopg v3 is required: python -m pip install 'psycopg[binary]>=3.2,<4'"
            )
        self._database_url = database_url

    # -- internal helpers ------------------------------------------------

    def _connect(self):
        # autocommit=True -> SELECTs don't even open a writable transaction.
        return psycopg.connect(self._database_url, autocommit=True)

    @staticmethod
    def _row_to_dict(cur, row) -> dict[str, Any]:
        cols = [d.name for d in cur.description]
        return dict(zip(cols, row))

    # -- SupabaseTransport read methods (pure SELECTs) -------------------

    def read_current_checkpoint(self) -> Mapping[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select checkpoint_id, payload_root_sha256, active_policy_hash,
                           verification_status, is_current
                    from destruktion_meta.chat_capsule_checkpoint
                    where is_current is true
                    order by created_at desc
                    limit 1
                    """
                )
                row = cur.fetchone()
                if row is None:
                    return {"status": "UNOBSERVED", "reason": "NO_CURRENT_CHECKPOINT"}
                result = self._row_to_dict(cur, row)
                result["is_current"] = bool(result.get("is_current"))
                result["source"] = self.store_kind
                return result

    def read_champion(self) -> Mapping[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select pointer_id, policy_hash, generation, promotion_receipt_hash
                    from destruktion_meta.champion_pointer
                    order by pointer_id
                    """
                )
                rows = cur.fetchall()
                champions = [self._row_to_dict(cur, r) for r in rows]
                if not champions:
                    return {"status": "UNOBSERVED", "reason": "NO_CHAMPION"}
                # pointer_id=1 is the canonical champion
                champion = champions[0]
                champion["source"] = self.store_kind
                return champion

    # -- mutation methods: fail-closed -----------------------------------

    def append_development_receipt(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        from .devfabric.providers.external import ConnectorPolicyError

        raise ConnectorPolicyError(
            "CANONICAL_MUTATION_BLOCKED",
            "read-only canonical transport: append_development_receipt refused",
        )

    def propose_checkpoint(
        self, payload: Mapping[str, Any], expected_parent: str
    ) -> Mapping[str, Any]:
        from .devfabric.providers.external import ConnectorPolicyError

        raise ConnectorPolicyError(
            "CANONICAL_MUTATION_BLOCKED",
            "read-only canonical transport: propose_checkpoint refused",
        )

    # -- convenience: identity + full readback ---------------------------

    def read_identity(self) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select current_database() database_name, current_user current_user, "
                    "session_user session_user, version() postgres_version"
                )
                row = cur.fetchone()
                return self._row_to_dict(cur, row)

    def readback(self) -> CanonicalReadback:
        return CanonicalReadback(
            checkpoint=dict(self.read_current_checkpoint()),
            champion=dict(self.read_champion()),
            identity=self.read_identity(),
            source=self.store_kind,
        )


# ---------------------------------------------------------------------------
# Anchor verification (boundary: canonical state must match expected)
# ---------------------------------------------------------------------------


def verify_against_expected(readback: CanonicalReadback) -> dict[str, Any]:
    cp = readback.checkpoint
    ch = readback.champion
    findings: list[str] = []

    cp_id_ok = cp.get("checkpoint_id") == EXPECTED_CHECKPOINT_ID
    cp_verified = cp.get("verification_status") == "VERIFIED"
    cp_current = bool(cp.get("is_current"))
    cp_policy_ok = cp.get("active_policy_hash") == EXPECTED_ACTIVE_POLICY_HASH

    ch_policy_ok = ch.get("policy_hash") == EXPECTED_ACTIVE_POLICY_HASH
    ch_gen_ok = int(ch.get("generation", -1)) == EXPECTED_CHAMPION_GENERATION

    if not cp_id_ok:
        findings.append(f"CHECKPOINT_ID_MISMATCH: got {cp.get('checkpoint_id')!r}")
    if not cp_verified:
        findings.append(f"CHECKPOINT_NOT_VERIFIED: {cp.get('verification_status')!r}")
    if not cp_current:
        findings.append("CHECKPOINT_NOT_CURRENT")
    if not cp_policy_ok:
        findings.append("ACTIVE_POLICY_HASH_MISMATCH")
    if not ch_policy_ok:
        findings.append("CHAMPION_POLICY_HASH_MISMATCH")
    if not ch_gen_ok:
        findings.append(f"CHAMPION_GENERATION_MISMATCH: got {ch.get('generation')!r}")

    return {
        "valid": not findings,
        "findings": findings,
        "expected": {
            "checkpoint_id": EXPECTED_CHECKPOINT_ID,
            "active_policy_hash": EXPECTED_ACTIVE_POLICY_HASH,
            "champion_generation": EXPECTED_CHAMPION_GENERATION,
        },
        "observed_checkpoint": cp,
        "observed_champion": ch,
        "identity": readback.identity,
        "source": readback.source,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _database_url_from_env() -> str:
    value = os.getenv("METAENGINE_DATABASE_URL", "").strip()
    if not value:
        raise CredentialsMissing(
            "METAENGINE_DATABASE_URL is not set. Reacquire it from Supabase Dashboard "
            "-> Project -> Connect and inject it via the trusted runtime environment. "
            "Do not paste it into chat or commit it to the project."
        )
    return value


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="MetaEngine READ-ONLY canonical Supabase connector (no mutation path)"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify", help="read-only canonical anchor verification")
    sub.add_parser("readback", help="print the full canonical readback (checkpoint+champion+identity)")
    a = ap.parse_args(argv)

    url = _database_url_from_env()
    transport = ReadOnlyCanonicalTransport(url)
    readback = transport.readback()

    if a.cmd == "readback":
        print(json.dumps(readback.as_dict(), indent=2, default=str))
        return 0

    # verify
    result = verify_against_expected(readback)
    print(json.dumps(result, indent=2, default=str))
    if not result["valid"]:
        raise CanonicalAnchorMismatch(
            "CANONICAL_ANCHOR_MISMATCH: " + "; ".join(result["findings"])
        )
    print("\nCANONICAL_VERIFY_PASS: live canonical state matches expected anchors (read-only, no mutation).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
