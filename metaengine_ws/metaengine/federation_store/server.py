"""METAENGINE — Local Federation Shadow Store server.

A small, dependency-free HTTP JSON-RPC server (stdlib ``http.server`` +
``sqlite3``) that backs the MetaEngine federation/canonical adapters.

It is **NOT** the canonical Supabase authority. It is a local shadow store
seeded from the bundled ``LIVE_CANONICAL_READBACK.json`` (point-in-time
readback), clearly labelled ``store_kind = LOCAL_FEDERATION_SHADOW_STORE``.

Protocol: ``POST /rpc`` with JSON body ``{"method": <name>, "params": {...}}``
returning ``{"result": <value>}`` or ``{"error": {"code": ..., "message": ...}}``.

Methods (mirror :class:`SupabaseTransport` + :class:`FederationRpcTransport`):

* ``read_current_checkpoint`` -> checkpoint dict
* ``read_champion`` -> champion dict
* ``read_store_manifest`` -> {store_kind, canonical_authority, seeded_from, ...}
* ``append_development_receipt`` (params: payload) -> {remote_id}
  — writes to the SHADOW store only.
* ``propose_checkpoint`` (params: payload, expected_parent) -> {applied, reason_code, remote_id?}
  — fail-closed: rejected unless ``--allow-canonical-mutation`` was passed
  at server start (a separately authorized gate).

Run::

    python3 -m metaengine.federation_store.server --port 5433 \
        --db ./metaengine_ws/var/federation_store.db \
        --seed metaengine_ws/.../LIVE_CANONICAL_READBACK.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping

STORE_KIND = "LOCAL_FEDERATION_SHADOW_STORE"
CANONICAL_AUTHORITY = False
SEED_SOURCE = "LIVE_CANONICAL_READBACK.json (bundled point-in-time readback)"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS store_manifest (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta_checkpoint (
    id                   INTEGER PRIMARY KEY CHECK (id = 1),
    checkpoint_id        TEXT NOT NULL,
    is_current           INTEGER NOT NULL,
    active_policy_hash   TEXT NOT NULL,
    payload_root_sha256  TEXT NOT NULL,
    verification_status  TEXT NOT NULL,
    seeded_from          TEXT NOT NULL,
    seeded_at            TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta_champion (
    id                          INTEGER PRIMARY KEY CHECK (id = 1),
    policy_hash                 TEXT NOT NULL,
    status                      TEXT NOT NULL,
    generation                  INTEGER NOT NULL,
    self_modifying_code_allowed INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS meta_counts (
    id                          INTEGER PRIMARY KEY CHECK (id = 1),
    open_epoch_count            INTEGER NOT NULL,
    finalized_epoch_count       INTEGER NOT NULL,
    promotion_receipt_count     INTEGER NOT NULL,
    adaptation_receipt_count    INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS development_receipts (
    remote_id    TEXT PRIMARY KEY,
    object_hash  TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    appended_at  TEXT NOT NULL,
    store_kind   TEXT NOT NULL
);
"""


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def seed_if_empty(conn: sqlite3.Connection, readback_path: Path) -> bool:
    """Seed the store from the bundled canonical readback if it is empty.

    Returns True if seeding occurred, False if the store was already seeded.
    """
    cur = conn.execute("SELECT COUNT(*) AS n FROM store_manifest")
    if cur.fetchone()["n"] > 0:
        return False

    readback = json.loads(readback_path.read_text(encoding="utf-8"))
    checkpoint = readback["checkpoint"]
    active_policy = readback["active_policy"]
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    conn.executemany(
        "INSERT OR REPLACE INTO store_manifest(key, value) VALUES (?, ?)",
        [
            ("store_kind", STORE_KIND),
            ("canonical_authority", "0"),
            ("seeded_from", SEED_SOURCE),
            ("seeded_at", now),
            ("seed_source_file", str(readback_path)),
            ("captured_at", str(readback.get("captured_at", ""))),
        ],
    )
    conn.execute(
        """
        INSERT INTO meta_checkpoint
            (id, checkpoint_id, is_current, active_policy_hash,
             payload_root_sha256, verification_status, seeded_from, seeded_at)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            checkpoint["checkpoint_id"],
            int(bool(checkpoint["is_current"])),
            checkpoint["active_policy_hash"],
            checkpoint["payload_root_sha256"],
            checkpoint["verification_status"],
            SEED_SOURCE,
            now,
        ),
    )
    conn.execute(
        """
        INSERT INTO meta_champion
            (id, policy_hash, status, generation, self_modifying_code_allowed)
        VALUES (1, ?, ?, ?, ?)
        """,
        (
            active_policy["policy_hash"],
            active_policy["status"],
            int(active_policy["generation"]),
            int(bool(active_policy["self_modifying_code_allowed"])),
        ),
    )
    conn.execute(
        """
        INSERT INTO meta_counts
            (id, open_epoch_count, finalized_epoch_count,
             promotion_receipt_count, adaptation_receipt_count)
        VALUES (1, ?, ?, ?, ?)
        """,
        (
            int(readback["open_epoch_count"]),
            int(readback["finalized_epoch_count"]),
            int(readback["promotion_receipt_count"]),
            int(readback["adaptation_receipt_count"]),
        ),
    )
    conn.commit()
    return True


# ---------------------------------------------------------------------------
# RPC method implementations
# ---------------------------------------------------------------------------


def _row_to_checkpoint(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "checkpoint_id": row["checkpoint_id"],
        "is_current": bool(row["is_current"]),
        "active_policy_hash": row["active_policy_hash"],
        "payload_root_sha256": row["payload_root_sha256"],
        "verification_status": row["verification_status"],
        "source": "LOCAL_FEDERATION_SHADOW_STORE",
        "seeded_from": row["seeded_from"],
        "seeded_at": row["seeded_at"],
    }


def read_current_checkpoint(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM meta_checkpoint WHERE id = 1").fetchone()
    if row is None:
        return {"status": "UNOBSERVED", "reason": "STORE_NOT_SEEDED"}
    return _row_to_checkpoint(row)


def read_champion(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM meta_champion WHERE id = 1").fetchone()
    if row is None:
        return {"status": "UNOBSERVED", "reason": "STORE_NOT_SEEDED"}
    return {
        "policy_hash": row["policy_hash"],
        "status": row["status"],
        "generation": int(row["generation"]),
        "self_modifying_code_allowed": bool(row["self_modifying_code_allowed"]),
        "source": "LOCAL_FEDERATION_SHADOW_STORE",
    }


def read_store_manifest(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute("SELECT key, value FROM store_manifest").fetchall()
    manifest = {row["key"]: row["value"] for row in rows}
    manifest["canonical_authority"] = manifest.get("canonical_authority") == "1"
    counts = conn.execute("SELECT * FROM meta_counts WHERE id = 1").fetchone()
    if counts is not None:
        manifest["open_epoch_count"] = int(counts["open_epoch_count"])
        manifest["finalized_epoch_count"] = int(counts["finalized_epoch_count"])
        manifest["promotion_receipt_count"] = int(counts["promotion_receipt_count"])
        manifest["adaptation_receipt_count"] = int(counts["adaptation_receipt_count"])
    manifest["development_receipt_count"] = int(
        conn.execute("SELECT COUNT(*) AS n FROM development_receipts").fetchone()["n"]
    )
    return manifest


def append_development_receipt(
    conn: sqlite3.Connection, payload: Mapping[str, Any]
) -> dict[str, Any]:
    from ..devfabric.codec import canonical_digest

    safe = dict(payload)
    object_hash = canonical_digest(safe)
    remote_id = f"shadow-{uuid.uuid4().hex}"
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn.execute(
        """
        INSERT INTO development_receipts
            (remote_id, object_hash, payload_json, appended_at, store_kind)
        VALUES (?, ?, ?, ?, ?)
        """,
        (remote_id, object_hash, json.dumps(safe, sort_keys=True), now, STORE_KIND),
    )
    conn.commit()
    return {"remote_id": remote_id, "store_kind": STORE_KIND, "object_hash": object_hash}


def propose_checkpoint(
    conn: sqlite3.Connection,
    payload: Mapping[str, Any],
    expected_parent: str,
    *,
    allow_canonical_mutation: bool,
) -> dict[str, Any]:
    """Fail-closed canonical checkpoint proposal.

    By default the shadow store refuses to mutate canonical checkpoint state.
    A separately authorized gate (``--allow-canonical-mutation``) is required
    to even record a proposed (still non-current, NON_CANONICAL) checkpoint.
    """
    if not allow_canonical_mutation:
        return {
            "applied": False,
            "reason_code": "CANONICAL_MUTATION_BLOCKED",
            "store_kind": STORE_KIND,
        }
    # Even when explicitly authorized, the proposed checkpoint is recorded as
    # NON_CANONICAL and is_current=False (mirroring the adapter contract).
    remote_id = f"shadow-propose-{uuid.uuid4().hex}"
    return {
        "applied": True,
        "reason_code": "OK_SHADOW_NON_CANONICAL",
        "remote_id": remote_id,
        "store_kind": STORE_KIND,
        "verification_status": "NON_CANONICAL",
        "is_current": False,
    }


# ---------------------------------------------------------------------------
# HTTP JSON-RPC server
# ---------------------------------------------------------------------------


def make_handler(db_path: Path, *, allow_canonical_mutation: bool):
    """Build an HTTP handler that opens a fresh SQLite connection per request.

    ThreadingHTTPServer spawns a thread per request; SQLite connections are
    thread-bound by default. Opening a short-lived connection per request is
    simple, thread-safe, and fine for this low-volume read-mostly store.
    """

    class _Handler(BaseHTTPRequestHandler):
        server_version = "MetaEngineFederationShadowStore/1"

        def log_message(self, fmt, *args):  # silence default logging
            pass

        def _send_json(self, status: int, body: dict[str, Any]) -> None:
            data = json.dumps(body, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Store-Kind", STORE_KIND)
            self.send_header(
                "X-Canonical-Authority", "true" if CANONICAL_AUTHORITY else "false"
            )
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.path in ("/", "/health"):
                with _connect(db_path) as conn:
                    manifest = read_store_manifest(conn)
                self._send_json(200, {"ok": True, **manifest})
                return
            if self.path == "/rpc/read_current_checkpoint":
                with _connect(db_path) as conn:
                    result = read_current_checkpoint(conn)
                self._send_json(200, {"result": result})
                return
            self._send_json(404, {"error": {"code": "NOT_FOUND", "message": self.path}})

        def do_POST(self) -> None:
            if self.path != "/rpc":
                self._send_json(404, {"error": {"code": "NOT_FOUND", "message": self.path}})
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                raw = self.rfile.read(length) if length else b"{}"
                envelope = json.loads(raw.decode("utf-8"))
            except (ValueError, json.JSONDecodeError) as exc:
                self._send_json(400, {"error": {"code": "BAD_JSON", "message": str(exc)}})
                return
            method = str(envelope.get("method", "")).strip()
            params = envelope.get("params", {}) or {}
            try:
                with _connect(db_path) as conn:
                    result = self._dispatch(conn, method, params)
            except Exception as exc:  # pragma: no cover - defensive
                self._send_json(
                    500, {"error": {"code": "INTERNAL", "message": str(exc)}}
                )
                return
            self._send_json(200, {"result": result})

        def _dispatch(
            self, conn: sqlite3.Connection, method: str, params: Mapping[str, Any]
        ) -> Any:
            if method == "read_current_checkpoint":
                return read_current_checkpoint(conn)
            if method == "read_champion":
                return read_champion(conn)
            if method == "read_store_manifest":
                return read_store_manifest(conn)
            if method == "append_development_receipt":
                return append_development_receipt(conn, params.get("payload", {}))
            if method == "propose_checkpoint":
                return propose_checkpoint(
                    conn,
                    params.get("payload", {}),
                    str(params.get("expected_parent", "")),
                    allow_canonical_mutation=allow_canonical_mutation,
                )
            raise ValueError(f"UNKNOWN_METHOD:{method}")

    return _Handler


def serve(
    *,
    port: int,
    db_path: Path,
    seed_path: Path,
    allow_canonical_mutation: bool = False,
    host: str = "127.0.0.1",
) -> None:
    # Seed once up-front in the main thread, then serve with per-request conns.
    with _connect(db_path) as conn:
        seeded = seed_if_empty(conn, seed_path)
        manifest = read_store_manifest(conn)
    status = "SEEDED" if seeded else "ALREADY_SEEDED"
    handler = make_handler(db_path, allow_canonical_mutation=allow_canonical_mutation)
    httpd = ThreadingHTTPServer((host, port), handler)
    print(
        f"[federation-store] listening on http://{host}:{port} "
        f"db={db_path} seed={status} store_kind={STORE_KIND} "
        f"canonical_authority={CANONICAL_AUTHORITY} checkpoint={manifest.get('seeded_from','')[:48]}"
    )
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MetaEngine local federation shadow store")
    ap.add_argument("--port", type=int, default=5433)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--db", required=True, help="path to the SQLite db file")
    ap.add_argument("--seed", required=True, help="path to LIVE_CANONICAL_READBACK.json")
    ap.add_argument(
        "--allow-canonical-mutation",
        action="store_true",
        help="SEPARATELY AUTHORIZED GATE: allow propose_checkpoint to record a "
        "NON_CANONICAL proposed checkpoint. Off by default (fail-closed).",
    )
    a = ap.parse_args(argv)
    serve(
        port=a.port,
        host=a.host,
        db_path=Path(a.db).resolve(),
        seed_path=Path(a.seed).resolve(),
        allow_canonical_mutation=a.allow_canonical_mutation,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
