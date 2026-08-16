from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from metaengine.devfabric.codec import canonical_bytes, to_primitive

from .finalization import EpochFinalization
from .types import CandidateEligibility, ConflictClass, SlotId


class FederationStore:
    """Non-canonical local SQLite mirror used to prove federation semantics."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self._initialize()

    def close(self) -> None:
        self.connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield self.connection
        except BaseException:
            self.connection.execute("ROLLBACK")
            raise
        else:
            self.connection.execute("COMMIT")

    def _initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS epoch (
                epoch_id TEXT PRIMARY KEY,
                base_checkpoint_id TEXT NOT NULL,
                policy_hash TEXT NOT NULL,
                catalog_hash TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'OPEN'
            );
            CREATE TABLE IF NOT EXISTS slot (
                epoch_id TEXT NOT NULL REFERENCES epoch(epoch_id) ON DELETE CASCADE,
                slot_id TEXT NOT NULL,
                lease_generation INTEGER NOT NULL DEFAULT 0 CHECK (lease_generation >= 0),
                slot_state TEXT NOT NULL DEFAULT 'ACTIVE',
                PRIMARY KEY (epoch_id, slot_id)
            );
            CREATE TABLE IF NOT EXISTS session (
                session_id TEXT PRIMARY KEY,
                epoch_id TEXT NOT NULL REFERENCES epoch(epoch_id) ON DELETE CASCADE,
                slot_id TEXT NOT NULL,
                lease_generation INTEGER NOT NULL CHECK (lease_generation >= 0),
                capsule_sha256 TEXT NOT NULL,
                protocol_version TEXT NOT NULL,
                role_profile_hash TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0 CHECK (revoked IN (0,1)),
                released_at TEXT,
                FOREIGN KEY (epoch_id, slot_id) REFERENCES slot(epoch_id, slot_id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_session_per_slot
            ON session(epoch_id, slot_id)
            WHERE revoked = 0 AND released_at IS NULL;

            CREATE TABLE IF NOT EXISTS task (
                task_hash TEXT PRIMARY KEY,
                epoch_id TEXT NOT NULL REFERENCES epoch(epoch_id) ON DELETE CASCADE,
                task_version INTEGER NOT NULL,
                owner_slot TEXT NOT NULL,
                lease_generation INTEGER NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS assignment (
                task_hash TEXT NOT NULL REFERENCES task(task_hash) ON DELETE CASCADE,
                session_id TEXT NOT NULL REFERENCES session(session_id),
                lease_generation INTEGER NOT NULL,
                assignment_state TEXT NOT NULL DEFAULT 'CLAIMED',
                PRIMARY KEY (task_hash, session_id, lease_generation)
            );
            CREATE TABLE IF NOT EXISTS candidate (
                candidate_hash TEXT PRIMARY KEY,
                task_hash TEXT NOT NULL REFERENCES task(task_hash) ON DELETE CASCADE,
                epoch_id TEXT NOT NULL,
                slot_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                lease_generation INTEGER NOT NULL,
                eligibility TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS review (
                review_hash TEXT PRIMARY KEY,
                candidate_hash TEXT NOT NULL REFERENCES candidate(candidate_hash) ON DELETE CASCADE,
                reviewer_slot TEXT NOT NULL,
                session_id TEXT NOT NULL,
                lease_generation INTEGER NOT NULL,
                verdict TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS conflict (
                conflict_hash TEXT PRIMARY KEY,
                epoch_id TEXT NOT NULL REFERENCES epoch(epoch_id) ON DELETE CASCADE,
                conflict_class TEXT NOT NULL,
                left_ref TEXT NOT NULL,
                right_ref TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS snapshot (
                snapshot_hash TEXT PRIMARY KEY,
                epoch_id TEXT NOT NULL REFERENCES epoch(epoch_id) ON DELETE CASCADE,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS integration_decision (
                decision_hash TEXT PRIMARY KEY,
                epoch_id TEXT NOT NULL REFERENCES epoch(epoch_id) ON DELETE CASCADE,
                candidate_hash TEXT,
                decision TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS finalization (
                finalization_hash TEXT PRIMARY KEY,
                epoch_id TEXT NOT NULL UNIQUE REFERENCES epoch(epoch_id),
                final_snapshot_hash TEXT NOT NULL REFERENCES snapshot(snapshot_hash),
                recovery_cut_hash TEXT NOT NULL,
                recovery_cut_json TEXT NOT NULL,
                finalized_by_session_id TEXT NOT NULL REFERENCES session(session_id),
                finalized_by_generation INTEGER NOT NULL,
                protocol_version TEXT NOT NULL
            );
            """
        )
        assignment_columns = {
            row[1] for row in self.connection.execute("PRAGMA table_info(assignment)").fetchall()
        }
        if "assignment_state" not in assignment_columns:
            self.connection.execute(
                "ALTER TABLE assignment ADD COLUMN assignment_state TEXT NOT NULL DEFAULT 'CLAIMED'"
            )

    @staticmethod
    def _payload(value: Any) -> str:
        return canonical_bytes(value).decode("utf-8")

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return None if row is None else dict(row)

    def _require_epoch_mutable(self, epoch_id: str) -> None:
        epoch = self.get_epoch(epoch_id)
        if epoch is None:
            raise KeyError(epoch_id)
        if epoch["state"] in {"CLOSED", "ABORTED"}:
            raise ValueError("FEDERATION_EPOCH_IMMUTABLE")

    @staticmethod
    def _finalization_values(finalization: EpochFinalization) -> tuple[Any, ...]:
        return (
            finalization.finalization_hash,
            finalization.epoch_id,
            finalization.final_snapshot_hash,
            finalization.recovery_cut_hash,
            canonical_bytes(finalization.recovery_cut).decode("utf-8"),
            finalization.finalized_by_session_id,
            finalization.finalized_by_generation,
            finalization.protocol_version,
        )

    def _insert_finalization(self, db: sqlite3.Connection, finalization: EpochFinalization) -> bool:
        existing = db.execute(
            "SELECT * FROM finalization WHERE epoch_id=?", (finalization.epoch_id,)
        ).fetchone()
        if existing is not None:
            if existing["finalization_hash"] == finalization.finalization_hash:
                return False
            raise ValueError("FEDERATION_FINALIZATION_CONFLICT")
        db.execute(
            """INSERT INTO finalization(
                finalization_hash, epoch_id, final_snapshot_hash, recovery_cut_hash, recovery_cut_json,
                finalized_by_session_id, finalized_by_generation, protocol_version
            ) VALUES(?,?,?,?,?,?,?,?)""",
            self._finalization_values(finalization),
        )
        return True

    def put_epoch(self, *, epoch_id: str, base_checkpoint_id: str, policy_hash: str, catalog_hash: str) -> None:
        with self.transaction() as db:
            db.execute(
                "INSERT INTO epoch(epoch_id, base_checkpoint_id, policy_hash, catalog_hash) VALUES(?,?,?,?)",
                (epoch_id, base_checkpoint_id, policy_hash, catalog_hash),
            )
            for slot in SlotId:
                db.execute(
                    "INSERT INTO slot(epoch_id, slot_id, lease_generation) VALUES(?,?,0)",
                    (epoch_id, slot.value),
                )

    def get_epoch(self, epoch_id: str) -> dict[str, Any] | None:
        return self._row(self.connection.execute("SELECT * FROM epoch WHERE epoch_id=?", (epoch_id,)).fetchone())

    def slot_generation(self, epoch_id: str, slot_id: SlotId) -> int:
        row = self.connection.execute(
            "SELECT lease_generation FROM slot WHERE epoch_id=? AND slot_id=?",
            (epoch_id, SlotId(slot_id).value),
        ).fetchone()
        if row is None:
            raise KeyError((epoch_id, slot_id))
        return int(row[0])

    def set_slot_generation(self, epoch_id: str, slot_id: SlotId, *, expected: int, new: int) -> bool:
        self._require_epoch_mutable(epoch_id)
        with self.transaction() as db:
            cur = db.execute(
                "UPDATE slot SET lease_generation=? WHERE epoch_id=? AND slot_id=? AND lease_generation=?",
                (new, epoch_id, SlotId(slot_id).value, expected),
            )
            return cur.rowcount == 1

    def put_session(
        self,
        *,
        session_id: str,
        epoch_id: str,
        slot_id: SlotId,
        lease_generation: int,
        capsule_sha256: str,
        protocol_version: str,
        role_profile_hash: str,
    ) -> None:
        self._require_epoch_mutable(epoch_id)
        self.connection.execute(
            """INSERT INTO session(
                session_id, epoch_id, slot_id, lease_generation, capsule_sha256, protocol_version, role_profile_hash
            ) VALUES(?,?,?,?,?,?,?)""",
            (
                session_id,
                epoch_id,
                SlotId(slot_id).value,
                int(lease_generation),
                capsule_sha256,
                protocol_version,
                role_profile_hash,
            ),
        )

    def active_session_for_slot(self, epoch_id: str, slot_id: SlotId) -> dict[str, Any] | None:
        return self._row(
            self.connection.execute(
                """SELECT * FROM session
                WHERE epoch_id=? AND slot_id=? AND revoked=0 AND released_at IS NULL""",
                (epoch_id, SlotId(slot_id).value),
            ).fetchone()
        )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        return self._row(self.connection.execute("SELECT * FROM session WHERE session_id=?", (session_id,)).fetchone())

    def release_session(self, session_id: str, *, expected_generation: int) -> bool:
        cur = self.connection.execute(
            """UPDATE session SET released_at='RELEASED'
            WHERE session_id=? AND lease_generation=? AND revoked=0 AND released_at IS NULL""",
            (session_id, expected_generation),
        )
        return cur.rowcount == 1

    def revoke_session(self, session_id: str, *, expected_generation: int) -> bool:
        cur = self.connection.execute(
            """UPDATE session SET revoked=1
            WHERE session_id=? AND lease_generation=? AND revoked=0 AND released_at IS NULL""",
            (session_id, expected_generation),
        )
        return cur.rowcount == 1

    def put_task(self, task: Any) -> None:
        self._require_epoch_mutable(task.epoch_id)
        self.connection.execute(
            """INSERT OR REPLACE INTO task(task_hash, epoch_id, task_version, owner_slot, lease_generation, payload_json)
            VALUES(?,?,?,?,?,?)""",
            (
                task.task_hash,
                task.epoch_id,
                task.task_version,
                task.owner_slot.value,
                task.lease_generation,
                self._payload(task),
            ),
        )

    def task_row(self, task_hash: str) -> dict[str, Any] | None:
        return self._row(self.connection.execute("SELECT * FROM task WHERE task_hash=?", (task_hash,)).fetchone())

    def list_task_rows(self, epoch_id: str) -> tuple[dict[str, Any], ...]:
        rows = self.connection.execute("SELECT * FROM task WHERE epoch_id=? ORDER BY task_hash", (epoch_id,)).fetchall()
        return tuple(dict(row) for row in rows)

    def put_assignment(self, *, task_hash: str, session_id: str, lease_generation: int) -> None:
        task = self.task_row(task_hash)
        if task is None:
            raise KeyError(task_hash)
        self._require_epoch_mutable(task["epoch_id"])
        self.connection.execute(
            """INSERT OR IGNORE INTO assignment(
                task_hash, session_id, lease_generation, assignment_state
            ) VALUES(?,?,?,'CLAIMED')""",
            (task_hash, session_id, int(lease_generation)),
        )

    def put_candidate(self, candidate: Any, *, eligibility: CandidateEligibility) -> None:
        self._require_epoch_mutable(candidate.epoch_id)
        self.connection.execute(
            """INSERT OR REPLACE INTO candidate(
                candidate_hash, task_hash, epoch_id, slot_id, session_id, lease_generation, eligibility, payload_json
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                candidate.candidate_hash,
                candidate.task_hash,
                candidate.epoch_id,
                candidate.slot_id.value,
                candidate.session_id,
                candidate.lease_generation,
                CandidateEligibility(eligibility).value,
                self._payload(candidate),
            ),
        )

    def candidate_row(self, candidate_hash: str) -> dict[str, Any] | None:
        return self._row(self.connection.execute("SELECT * FROM candidate WHERE candidate_hash=?", (candidate_hash,)).fetchone())

    def list_candidate_rows(self, epoch_id: str) -> tuple[dict[str, Any], ...]:
        rows = self.connection.execute(
            "SELECT * FROM candidate WHERE epoch_id=? ORDER BY candidate_hash", (epoch_id,)
        ).fetchall()
        return tuple(dict(row) for row in rows)

    def put_review(self, review: Any) -> None:
        candidate = self.candidate_row(review.candidate_hash)
        if candidate is None:
            raise KeyError(review.candidate_hash)
        self._require_epoch_mutable(candidate["epoch_id"])
        self.connection.execute(
            """INSERT OR REPLACE INTO review(
                review_hash, candidate_hash, reviewer_slot, session_id, lease_generation, verdict, payload_json
            ) VALUES(?,?,?,?,?,?,?)""",
            (
                review.review_hash,
                review.candidate_hash,
                review.reviewer_slot.value,
                review.session_id,
                review.lease_generation,
                review.verdict.value,
                self._payload(review),
            ),
        )

    def list_review_rows(self, candidate_hash: str) -> tuple[dict[str, Any], ...]:
        rows = self.connection.execute(
            "SELECT * FROM review WHERE candidate_hash=? ORDER BY review_hash", (candidate_hash,)
        ).fetchall()
        return tuple(dict(row) for row in rows)

    def put_conflict(self, *, conflict_hash: str, epoch_id: str, conflict_class: ConflictClass, left_ref: str, right_ref: str, payload: Any) -> None:
        self._require_epoch_mutable(epoch_id)
        self.connection.execute(
            """INSERT OR REPLACE INTO conflict(conflict_hash, epoch_id, conflict_class, left_ref, right_ref, payload_json)
            VALUES(?,?,?,?,?,?)""",
            (conflict_hash, epoch_id, ConflictClass(conflict_class).value, left_ref, right_ref, self._payload(payload)),
        )

    def put_snapshot(self, *, snapshot_hash: str, epoch_id: str, payload: Any) -> None:
        self._require_epoch_mutable(epoch_id)
        self.connection.execute(
            "INSERT OR REPLACE INTO snapshot(snapshot_hash, epoch_id, payload_json) VALUES(?,?,?)",
            (snapshot_hash, epoch_id, self._payload(payload)),
        )

    def list_assignment_rows(self, epoch_id: str) -> tuple[dict[str, Any], ...]:
        rows = self.connection.execute(
            """SELECT a.*, (a.task_hash || ':' || a.session_id || ':' || a.lease_generation) AS assignment_id
            FROM assignment a JOIN task t ON t.task_hash=a.task_hash
            WHERE t.epoch_id=? ORDER BY assignment_id""",
            (epoch_id,),
        ).fetchall()
        return tuple(dict(row) for row in rows)

    def list_review_rows_for_epoch(self, epoch_id: str) -> tuple[dict[str, Any], ...]:
        rows = self.connection.execute(
            """SELECT r.* FROM review r JOIN candidate c ON c.candidate_hash=r.candidate_hash
            WHERE c.epoch_id=? ORDER BY r.review_hash""",
            (epoch_id,),
        ).fetchall()
        return tuple(dict(row) for row in rows)

    def list_conflict_rows(self, epoch_id: str) -> tuple[dict[str, Any], ...]:
        rows = self.connection.execute(
            "SELECT * FROM conflict WHERE epoch_id=? ORDER BY conflict_hash", (epoch_id,)
        ).fetchall()
        return tuple(dict(row) for row in rows)

    def put_integration_decision(
        self, *, decision_hash: str, epoch_id: str, candidate_hash: str | None, decision: str, reason: str = ""
    ) -> None:
        self._require_epoch_mutable(epoch_id)
        self.connection.execute(
            """INSERT OR REPLACE INTO integration_decision(
                decision_hash, epoch_id, candidate_hash, decision, reason
            ) VALUES(?,?,?,?,?)""",
            (decision_hash, epoch_id, candidate_hash, decision, reason),
        )

    def list_integration_decision_rows(self, epoch_id: str) -> tuple[dict[str, Any], ...]:
        rows = self.connection.execute(
            "SELECT * FROM integration_decision WHERE epoch_id=? ORDER BY decision_hash", (epoch_id,)
        ).fetchall()
        return tuple(dict(row) for row in rows)

    def list_session_rows(self, epoch_id: str) -> tuple[dict[str, Any], ...]:
        rows = self.connection.execute(
            "SELECT * FROM session WHERE epoch_id=? ORDER BY slot_id, session_id", (epoch_id,)
        ).fetchall()
        return tuple(dict(row) for row in rows)

    def snapshot_row(self, snapshot_hash: str) -> dict[str, Any] | None:
        return self._row(
            self.connection.execute("SELECT * FROM snapshot WHERE snapshot_hash=?", (snapshot_hash,)).fetchone()
        )

    def put_finalization(self, finalization: EpochFinalization) -> bool:
        with self.transaction() as db:
            return self._insert_finalization(db, finalization)

    def get_finalization(self, epoch_id: str) -> dict[str, Any] | None:
        row = self._row(
            self.connection.execute("SELECT * FROM finalization WHERE epoch_id=?", (epoch_id,)).fetchone()
        )
        if row is None:
            return None
        row["recovery_cut"] = json.loads(row.pop("recovery_cut_json"))
        return row

    def close_epoch(self, epoch_id: str, *, finalization: EpochFinalization) -> None:
        if finalization.epoch_id != epoch_id:
            raise ValueError("FEDERATION_FINALIZATION_EPOCH_MISMATCH")
        with self.transaction() as db:
            epoch = db.execute("SELECT state FROM epoch WHERE epoch_id=?", (epoch_id,)).fetchone()
            if epoch is None:
                raise KeyError(epoch_id)
            if epoch["state"] in {"CLOSED", "ABORTED"}:
                existing = db.execute(
                    "SELECT finalization_hash FROM finalization WHERE epoch_id=?", (epoch_id,)
                ).fetchone()
                if existing is not None and existing["finalization_hash"] == finalization.finalization_hash:
                    return
                raise ValueError("FEDERATION_EPOCH_IMMUTABLE")
            if epoch["state"] not in {"OPEN", "INTEGRATING"}:
                raise ValueError("FEDERATION_EPOCH_NOT_FINALIZABLE")
            self._insert_finalization(db, finalization)
            db.execute("UPDATE epoch SET state='CLOSED' WHERE epoch_id=?", (epoch_id,))
            db.execute(
                """UPDATE session SET revoked=1, released_at='RELEASED'
                WHERE epoch_id=? AND revoked=0 AND released_at IS NULL""",
                (epoch_id,),
            )
            db.execute(
                """UPDATE assignment SET assignment_state='RELEASED'
                WHERE assignment_state='CLAIMED' AND task_hash IN (
                    SELECT task_hash FROM task WHERE epoch_id=?
                )""",
                (epoch_id,),
            )

    def latest_snapshot_row(self, epoch_id: str) -> dict[str, Any] | None:
        return self._row(
            self.connection.execute(
                "SELECT * FROM snapshot WHERE epoch_id=? ORDER BY snapshot_hash DESC LIMIT 1", (epoch_id,)
            ).fetchone()
        )
