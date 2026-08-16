from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable


class PerformanceStore:
    """Local measured priors for routing; never a safety or verification authority."""

    def __init__(self, path: str | Path, *, alpha: float = 0.25):
        if not 0.0 < alpha <= 1.0:
            raise ValueError("alpha must be in (0, 1]")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.alpha = float(alpha)
        with sqlite3.connect(self.path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS provider_performance (
                    provider_id TEXT PRIMARY KEY,
                    observations INTEGER NOT NULL,
                    ewma REAL NOT NULL,
                    successes INTEGER NOT NULL
                )
                """
            )

    def record(self, provider_id: str, *, quality: float, success: bool) -> float:
        quality = float(quality)
        if not 0.0 <= quality <= 1.0:
            raise ValueError("quality must be in [0, 1]")
        sample = quality if success else quality * 0.25
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT observations, ewma, successes FROM provider_performance WHERE provider_id = ?",
                (provider_id,),
            ).fetchone()
            if row is None:
                observations, ewma, successes = 1, sample, int(bool(success))
                conn.execute(
                    "INSERT INTO provider_performance(provider_id, observations, ewma, successes) VALUES (?, ?, ?, ?)",
                    (provider_id, observations, ewma, successes),
                )
            else:
                observations = int(row[0]) + 1
                ewma = self.alpha * sample + (1.0 - self.alpha) * float(row[1])
                successes = int(row[2]) + int(bool(success))
                conn.execute(
                    "UPDATE provider_performance SET observations = ?, ewma = ?, successes = ? WHERE provider_id = ?",
                    (observations, ewma, successes, provider_id),
                )
        return float(ewma)

    def score(self, provider_id: str) -> float:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                "SELECT ewma FROM provider_performance WHERE provider_id = ?",
                (provider_id,),
            ).fetchone()
        return float(row[0]) if row is not None else 0.0

    def priors(self) -> dict[str, float]:
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute("SELECT provider_id, ewma FROM provider_performance ORDER BY provider_id").fetchall()
        return {str(provider_id): float(ewma) for provider_id, ewma in rows}

    def rank(self, provider_ids: Iterable[str]) -> tuple[str, ...]:
        ids = tuple(str(x) for x in provider_ids)
        return tuple(sorted(ids, key=lambda provider_id: (-self.score(provider_id), provider_id)))
