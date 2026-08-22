from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections.abc import Iterator
from typing import Any


_PERSISTED_PROFILE_KEYS = {
    "hard_constraints", "preferences", "preference_items", "recognized", "answered_facets",
}


class ConversationMemoryService:
    """Store only an opt-in structured preference profile, never raw chat or family data."""

    def __init__(self, database_path: Path, retention_days: int = 180):
        self.database_path = database_path
        self.retention_days = retention_days
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS conversation_memory (
                    anonymous_session_id TEXT PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    @staticmethod
    def _session_id(value: uuid.UUID | str) -> str:
        return str(uuid.UUID(str(value)))

    @staticmethod
    def _safe_profile(profile: dict[str, Any]) -> dict[str, Any]:
        safe = {key: profile[key] for key in _PERSISTED_PROFILE_KEYS if key in profile}
        safe.setdefault("hard_constraints", {})
        safe.setdefault("preferences", {})
        serialized = json.dumps(safe, sort_keys=True, separators=(",", ":"))
        if len(serialized.encode("utf-8")) > 32_000:
            raise ValueError("Preference memory exceeds the 32 KB limit")
        return json.loads(serialized)

    def save(self, session_id: uuid.UUID | str, profile: dict[str, Any]) -> None:
        safe = self._safe_profile(profile)
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO conversation_memory
                   (anonymous_session_id, profile_json, updated_at) VALUES (?, ?, ?)
                   ON CONFLICT(anonymous_session_id) DO UPDATE SET
                   profile_json = excluded.profile_json, updated_at = excluded.updated_at""",
                (
                    self._session_id(session_id),
                    json.dumps(safe, sort_keys=True, separators=(",", ":")),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def restore(self, session_id: uuid.UUID | str) -> dict[str, Any] | None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        with self._connect() as connection:
            connection.execute("DELETE FROM conversation_memory WHERE updated_at < ?", (cutoff.isoformat(),))
            row = connection.execute(
                "SELECT profile_json FROM conversation_memory WHERE anonymous_session_id = ?",
                (self._session_id(session_id),),
            ).fetchone()
        return json.loads(row["profile_json"]) if row else None

    def forget(self, session_id: uuid.UUID | str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM conversation_memory WHERE anonymous_session_id = ?",
                (self._session_id(session_id),),
            )
