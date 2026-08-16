from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .codec import canonical_digest, to_primitive


class JournalConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class JournalReceipt:
    seq: int
    event_id: str
    event_hash: str
    parent_hash: str


@dataclass(frozen=True)
class OutboxItem:
    event_id: str
    kind: str
    object_id: str
    event_hash: str
    replay_status: str
    remote_receipt_hash: str | None


class Journal:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    parent_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS outbox (
                    event_id TEXT PRIMARY KEY REFERENCES events(event_id),
                    replay_status TEXT NOT NULL DEFAULT 'PENDING',
                    remote_receipt_hash TEXT
                );
                """
            )

    @staticmethod
    def _event_hash(*, kind: str, object_id: str, payload_hash: str, parent_hash: str) -> str:
        return canonical_digest(
            {
                "kind": kind,
                "object_id": object_id,
                "payload_hash": payload_hash,
                "parent_hash": parent_hash,
            }
        )

    def append(self, kind: str, object_id: str, payload: Any) -> JournalReceipt:
        primitive = to_primitive(payload)
        payload_json = json.dumps(primitive, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        payload_hash = canonical_digest(primitive)
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            parent_hash = row["event_hash"] if row else "0" * 64
            event_hash = self._event_hash(
                kind=kind,
                object_id=object_id,
                payload_hash=payload_hash,
                parent_hash=parent_hash,
            )
            event_id = f"evt-{event_hash[:20]}"
            cur = conn.execute(
                """
                INSERT INTO events(event_id, kind, object_id, payload_json, payload_hash, parent_hash, event_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, kind, object_id, payload_json, payload_hash, parent_hash, event_hash),
            )
            conn.execute("INSERT INTO outbox(event_id) VALUES (?)", (event_id,))
            conn.commit()
            return JournalReceipt(
                seq=int(cur.lastrowid),
                event_id=event_id,
                event_hash=event_hash,
                parent_hash=parent_hash,
            )
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def verify_chain(self) -> list[str]:
        errors: list[str] = []
        expected_parent = "0" * 64
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM events ORDER BY seq").fetchall()
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except json.JSONDecodeError:
                errors.append(f"seq={row['seq']}:INVALID_PAYLOAD_JSON")
                expected_parent = row["event_hash"]
                continue
            payload_hash = canonical_digest(payload)
            if payload_hash != row["payload_hash"]:
                errors.append(f"seq={row['seq']}:PAYLOAD_HASH_MISMATCH")
            if row["parent_hash"] != expected_parent:
                errors.append(f"seq={row['seq']}:PARENT_HASH_MISMATCH")
            expected_event_hash = self._event_hash(
                kind=row["kind"],
                object_id=row["object_id"],
                payload_hash=payload_hash,
                parent_hash=row["parent_hash"],
            )
            if expected_event_hash != row["event_hash"]:
                errors.append(f"seq={row['seq']}:EVENT_HASH_MISMATCH")
            expected_parent = row["event_hash"]
        return errors

    def pending_outbox(self) -> tuple[OutboxItem, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT e.event_id, e.kind, e.object_id, e.event_hash,
                       o.replay_status, o.remote_receipt_hash
                FROM outbox o JOIN events e USING(event_id)
                WHERE o.replay_status = 'PENDING'
                ORDER BY e.seq
                """
            ).fetchall()
        return tuple(OutboxItem(**dict(row)) for row in rows)

    def mark_replayed(self, event_id: str, remote_receipt_hash: str) -> None:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT replay_status, remote_receipt_hash FROM outbox WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if row is None:
                raise KeyError(event_id)
            if row["replay_status"] == "REPLAYED":
                if row["remote_receipt_hash"] != remote_receipt_hash:
                    raise JournalConflict(f"conflicting replay receipt for {event_id}")
                conn.commit()
                return
            conn.execute(
                "UPDATE outbox SET replay_status = 'REPLAYED', remote_receipt_hash = ? WHERE event_id = ?",
                (remote_receipt_hash, event_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
