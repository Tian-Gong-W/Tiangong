from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .model import KnowledgeRecord


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class KnowledgeStore:
    """Knowledge persistence with SQLite fallback and shared PostgreSQL support.

    SQLite remains the zero-configuration development backend. Production workers
    may share a PostgreSQL database by setting ``TONMEN_KNOWLEDGE_DATABASE_URL``.
    """

    def __init__(self, path: Path | str, *, database_url: str | None = None) -> None:
        self.path = Path(path)
        self.database_url = str(database_url or "").strip()

    @classmethod
    def for_workspace(cls, workspace: Path | str) -> "KnowledgeStore":
        return cls(
            Path(workspace) / "knowledge" / "knowledge.db",
            database_url=os.getenv("TONMEN_KNOWLEDGE_DATABASE_URL", "").strip() or None,
        )

    @property
    def backend(self) -> str:
        if self.database_url.startswith(("postgresql://", "postgres://")):
            return "postgres"
        return "sqlite"

    def _connect(self):
        if self.backend == "postgres":
            try:
                import psycopg
            except ImportError as exc:
                raise RuntimeError(
                    "PostgreSQL knowledge storage requires psycopg; install project dependencies"
                ) from exc
            connection = psycopg.connect(self.database_url)
            self._ensure_schema(connection)
            return connection

        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        self._ensure_schema(connection)
        return connection

    def _ensure_schema(self, connection) -> None:
        if self.backend == "postgres":
            statements = (
                """
                CREATE TABLE IF NOT EXISTS knowledge_records (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS knowledge_watch_targets (
                    target_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS knowledge_ingestion_runs (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS knowledge_peer_comparisons (
                    id TEXT PRIMARY KEY,
                    target_key TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE INDEX IF NOT EXISTS idx_knowledge_peer_target_updated
                ON knowledge_peer_comparisons (target_key, updated_at DESC)
                """,
            )
        else:
            statements = (
                """
                CREATE TABLE IF NOT EXISTS knowledge_records (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS knowledge_watch_targets (
                    target_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS knowledge_ingestion_runs (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS knowledge_peer_comparisons (
                    id TEXT PRIMARY KEY,
                    target_key TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE INDEX IF NOT EXISTS idx_knowledge_peer_target_updated
                ON knowledge_peer_comparisons (target_key, updated_at DESC)
                """,
            )
        for statement in statements:
            connection.execute(statement)
        connection.commit()

    def _ph(self) -> str:
        return "%s" if self.backend == "postgres" else "?"

    def upsert(self, record: KnowledgeRecord) -> None:
        payload = json.dumps(record.as_dict(), ensure_ascii=False, sort_keys=True)
        ph = self._ph()
        with self._connect() as connection:
            connection.execute(
                f"""
                INSERT INTO knowledge_records (id, payload, updated_at)
                VALUES ({ph}, {ph}, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (record.id, payload),
            )

    def upsert_many(self, records) -> None:
        rows = [
            (record.id, json.dumps(record.as_dict(), ensure_ascii=False, sort_keys=True))
            for record in records
        ]
        if not rows:
            return
        ph = self._ph()
        query = f"""
            INSERT INTO knowledge_records (id, payload, updated_at)
            VALUES ({ph}, {ph}, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = CURRENT_TIMESTAMP
        """
        with self._connect() as connection:
            if self.backend == "postgres":
                with connection.cursor() as cursor:
                    cursor.executemany(query, rows)
            else:
                connection.executemany(query, rows)

    @staticmethod
    def _decode_rows(rows) -> tuple[dict[str, Any], ...]:
        values: list[dict[str, Any]] = []
        for row in rows:
            payload = row[0]
            try:
                data = json.loads(payload)
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                values.append(data)
        return tuple(values)

    def all(self) -> tuple[KnowledgeRecord, ...]:
        if self.backend == "sqlite" and not self.path.exists():
            return ()
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT payload FROM knowledge_records ORDER BY updated_at DESC, id ASC"
                ).fetchall()
        except Exception:
            if self.backend == "sqlite":
                return ()
            raise
        records: list[KnowledgeRecord] = []
        for data in self._decode_rows(rows):
            try:
                records.append(KnowledgeRecord.from_dict(data))
            except (TypeError, ValueError):
                continue
        return tuple(records)

    def count(self) -> int:
        if self.backend == "sqlite" and not self.path.exists():
            return 0
        try:
            with self._connect() as connection:
                row = connection.execute("SELECT COUNT(*) FROM knowledge_records").fetchone()
        except Exception:
            if self.backend == "sqlite":
                return 0
            raise
        return int(row[0]) if row else 0

    def upsert_watch_target(self, target_key: str, payload: Mapping[str, Any]) -> None:
        data = dict(payload)
        data.setdefault("target_key", target_key)
        data["updated_at"] = _utc_iso()
        encoded = json.dumps(data, ensure_ascii=False, sort_keys=True)
        ph = self._ph()
        with self._connect() as connection:
            connection.execute(
                f"""
                INSERT INTO knowledge_watch_targets (target_key, payload, updated_at)
                VALUES ({ph}, {ph}, CURRENT_TIMESTAMP)
                ON CONFLICT(target_key) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (target_key, encoded),
            )

    def watch_targets(self) -> tuple[dict[str, Any], ...]:
        if self.backend == "sqlite" and not self.path.exists():
            return ()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM knowledge_watch_targets ORDER BY updated_at DESC, target_key ASC"
            ).fetchall()
        return self._decode_rows(rows)

    def save_ingestion_run(self, run_id: str, payload: Mapping[str, Any]) -> None:
        data = dict(payload)
        data.setdefault("id", run_id)
        encoded = json.dumps(data, ensure_ascii=False, sort_keys=True)
        ph = self._ph()
        with self._connect() as connection:
            connection.execute(
                f"""
                INSERT INTO knowledge_ingestion_runs (id, payload, updated_at)
                VALUES ({ph}, {ph}, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (run_id, encoded),
            )

    def save_peer_comparison(
        self,
        comparison_id: str,
        target_key: str,
        payload: Mapping[str, Any],
    ) -> None:
        data = dict(payload)
        data.setdefault("id", comparison_id)
        data.setdefault("target_key", target_key)
        encoded = json.dumps(data, ensure_ascii=False, sort_keys=True)
        ph = self._ph()
        with self._connect() as connection:
            connection.execute(
                f"""
                INSERT INTO knowledge_peer_comparisons (id, target_key, payload, updated_at)
                VALUES ({ph}, {ph}, {ph}, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    target_key = excluded.target_key,
                    payload = excluded.payload,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (comparison_id, target_key, encoded),
            )

    def latest_peer_comparisons(
        self,
        target_key: str,
        *,        limit: int = 12,
    ) -> tuple[dict[str, Any], ...]:
        if self.backend == "sqlite" and not self.path.exists():
            return ()
        ph = self._ph()
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT payload
                FROM knowledge_peer_comparisons
                WHERE target_key = {ph}
                ORDER BY updated_at DESC
                LIMIT {ph}
                """,
                (target_key, max(1, int(limit))),
            ).fetchall()
        return self._decode_rows(rows)
