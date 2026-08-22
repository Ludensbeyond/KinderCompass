from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Iterator
from typing import Any

from SystemCode.src.backend.domain.models import ChatFeedbackRequest


class ChatAnswerNotFoundError(LookupError):
    pass


class ChatFeedbackService:
    """Measure answer usefulness without retaining question or answer text."""

    def __init__(self, database_path: Path):
        self.database_path = database_path
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
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS chat_answer_snapshots (
                    answer_id TEXT PRIMARY KEY,
                    intent TEXT NOT NULL,
                    evidence_category TEXT NOT NULL,
                    answer_method TEXT NOT NULL,
                    citation_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chat_answer_feedback (
                    feedback_id TEXT PRIMARY KEY,
                    answer_id TEXT NOT NULL,
                    anonymous_session_id TEXT NOT NULL,
                    helpful INTEGER NOT NULL,
                    reason TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(answer_id, anonymous_session_id),
                    FOREIGN KEY(answer_id) REFERENCES chat_answer_snapshots(answer_id)
                );
            """)

    def record_answer(self, result: dict[str, Any]) -> str:
        answer_id = str(uuid.uuid4())
        profile = result.get("profile") or {}
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO chat_answer_snapshots
                   (answer_id, intent, evidence_category, answer_method, citation_count, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    answer_id,
                    str(profile.get("intent") or result.get("status") or "unknown")[:80],
                    str(result.get("evidence_category") or "unknown")[:40],
                    str(result.get("answer_method") or result.get("web_answer_method") or profile.get("intent_method") or "deterministic")[:40],
                    len(result.get("citations") or []),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return answer_id

    def record_feedback(self, request: ChatFeedbackRequest) -> str:
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM chat_answer_snapshots WHERE answer_id = ?", (str(request.answer_id),)
            ).fetchone()
            if not exists:
                raise ChatAnswerNotFoundError("Chat answer snapshot was not found")
            feedback_id = str(uuid.uuid4())
            connection.execute(
                """INSERT INTO chat_answer_feedback
                   (feedback_id, answer_id, anonymous_session_id, helpful, reason, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(answer_id, anonymous_session_id) DO UPDATE SET
                   feedback_id = excluded.feedback_id, helpful = excluded.helpful,
                   reason = excluded.reason, created_at = excluded.created_at""",
                (
                    feedback_id, str(request.answer_id), str(request.anonymous_session_id),
                    int(request.helpful), request.reason, datetime.now(timezone.utc).isoformat(),
                ),
            )
        return feedback_id

    def summary(self) -> dict[str, Any]:
        with self._connect() as connection:
            rows = connection.execute("""
                SELECT s.intent, s.evidence_category, COUNT(*) AS responses,
                       SUM(f.helpful) AS helpful_responses
                FROM chat_answer_feedback f
                JOIN chat_answer_snapshots s ON s.answer_id = f.answer_id
                GROUP BY s.intent, s.evidence_category
                ORDER BY responses DESC, s.intent, s.evidence_category
            """).fetchall()
        segments = [
            {
                "intent": row["intent"], "evidence_category": row["evidence_category"],
                "responses": row["responses"], "helpful_responses": row["helpful_responses"],
                "helpful_rate": row["helpful_responses"] / row["responses"],
            }
            for row in rows
        ]
        total = sum(item["responses"] for item in segments)
        helpful = sum(item["helpful_responses"] for item in segments)
        return {
            "responses": total,
            "helpful_responses": helpful,
            "helpful_rate": helpful / total if total else None,
            "segments": segments,
        }
