from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .model import KnowledgeRecord


class KnowledgeStore:
    """Small local knowledge database with atomic record upserts."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    @classmethod
    def for_workspace(cls, workspace: Path | str) -> "KnowledgeStore":
        return cls(Path(workspace) / "knowledge" / "knowledge.db")

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_records (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        return connection

    def upsert(self, record: KnowledgeRecord) -> None:
        payload = json.dumps(record.as_dict(), ensure_ascii=False, sort_keys=True)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO knowledge_records (id, payload, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
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
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO knowledge_records (id, payload, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = CURRENT_TIMESTAMP
                """,
                rows,
            )

    def all(self) -> tuple[KnowledgeRecord, ...]:
        if not self.path.exists():
            return ()
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT payload FROM knowledge_records ORDER BY updated_at DESC, id ASC"
                ).fetchall()
        except sqlite3.DatabaseError:
            return ()
        records: list[KnowledgeRecord] = []
        for (payload,) in rows:
            try:
                data = json.loads(payload)
                if isinstance(data, dict):
                    records.append(KnowledgeRecord.from_dict(data))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        return tuple(records)

    def count(self) -> int:
        if not self.path.exists():
            return 0
        try:
            with self._connect() as connection:
                row = connection.execute("SELECT COUNT(*) FROM knowledge_records").fetchone()
        except sqlite3.DatabaseError:
            return 0
        return int(row[0]) if row else 0
