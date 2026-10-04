from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Iterator

from SystemCode.src.backend.domain.catalogue import ParentRatingSummary, SchoolReview
from SystemCode.src.backend.domain.models import SchoolRatingRequest


class SchoolRatingService:
    """Persist consented, anonymous first-party parent ratings of schools."""

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
                CREATE TABLE IF NOT EXISTS school_ratings (
                    rating_id TEXT PRIMARY KEY,
                    school_id TEXT NOT NULL,
                    anonymous_session_id TEXT NOT NULL,
                    overall INTEGER NOT NULL CHECK (overall BETWEEN 1 AND 5),
                    teachers INTEGER,
                    communication INTEGER,
                    facilities INTEGER,
                    food INTEGER,
                    value INTEGER,
                    relationship TEXT NOT NULL,
                    tags_json TEXT,
                    review_text TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(school_id, anonymous_session_id)
                );
            """)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(school_ratings)")}
            if "review_text" not in columns:
                connection.execute("ALTER TABLE school_ratings ADD COLUMN review_text TEXT")

    @staticmethod
    def _empty_summary(school_id: str) -> ParentRatingSummary:
        return ParentRatingSummary.model_validate({
            "school_id": school_id,
            "average": None,
            "count": 0,
        })

    @staticmethod
    def _summary_from_row(school_id: str, row: sqlite3.Row | None) -> ParentRatingSummary:
        if row is None or not row["count"]:
            return SchoolRatingService._empty_summary(school_id)
        return ParentRatingSummary.model_validate({
            "school_id": school_id,
            "average": round(float(row["average"]), 1),
            "count": int(row["count"]),
        })

    @staticmethod
    def _clean_review(value: str | None) -> str | None:
        text = " ".join((value or "").split())
        return text or None

    def _written_reviews(
        self, connection: sqlite3.Connection, school_ids: list[str]
    ) -> dict[str, list[dict[str, str | int]]]:
        grouped: dict[str, list[dict[str, str | int]]] = {school_id: [] for school_id in school_ids}
        if not school_ids:
            return grouped
        placeholders = ",".join("?" * len(school_ids))
        rows = connection.execute(
            f"""SELECT school_id, overall, relationship, review_text, created_at
                FROM school_ratings
                WHERE school_id IN ({placeholders})
                  AND review_text IS NOT NULL
                  AND length(trim(review_text)) > 0
                ORDER BY created_at DESC""",
            school_ids,
        ).fetchall()
        for row in rows:
            grouped[row["school_id"]].append({
                "overall": int(row["overall"]),
                "relationship": row["relationship"],
                "review_text": row["review_text"],
                "created_at": row["created_at"],
            })
        return grouped

    def _with_reviews(
        self, summaries: dict[str, ParentRatingSummary]
    ) -> dict[str, ParentRatingSummary]:
        if not summaries:
            return summaries
        with self._connect() as connection:
            reviews = self._written_reviews(connection, list(summaries))
        return {
            school_id: summary.model_copy(update={
                "reviews": [SchoolReview.model_validate(item) for item in reviews.get(school_id, [])],
            })
            for school_id, summary in summaries.items()
        }

    def record(self, school_id: str, request: SchoolRatingRequest) -> tuple[str, ParentRatingSummary]:
        rating_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        review_text = self._clean_review(request.review_text)
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO school_ratings
                   (rating_id, school_id, anonymous_session_id, overall, teachers,
                    communication, facilities, food, value, relationship, tags_json,
                    review_text, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(school_id, anonymous_session_id) DO UPDATE SET
                   rating_id = excluded.rating_id, overall = excluded.overall,
                   teachers = excluded.teachers, communication = excluded.communication,
                   facilities = excluded.facilities, food = excluded.food,
                   value = excluded.value, relationship = excluded.relationship,
                   tags_json = excluded.tags_json, review_text = excluded.review_text,
                   created_at = excluded.created_at""",
                (
                    rating_id,
                    school_id,
                    str(request.anonymous_session_id),
                    request.overall,
                    request.teachers,
                    request.communication,
                    request.facilities,
                    request.food,
                    request.value,
                    request.relationship,
                    json.dumps(request.tags, separators=(",", ":")),
                    review_text,
                    created_at,
                ),
            )
        return rating_id, self.summary(school_id)

    def summary(self, school_id: str) -> ParentRatingSummary:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT AVG(overall) AS average, COUNT(*) AS count
                   FROM school_ratings WHERE school_id = ?""",
                (school_id,),
            ).fetchone()
        return self._with_reviews({
            school_id: self._summary_from_row(school_id, row),
        })[school_id]

    def summaries(self, school_ids: list[str]) -> dict[str, ParentRatingSummary]:
        unique = list(dict.fromkeys(school_ids))
        if not unique:
            return {}
        placeholders = ",".join("?" * len(unique))
        with self._connect() as connection:
            rows = connection.execute(
                f"""SELECT school_id, AVG(overall) AS average, COUNT(*) AS count
                    FROM school_ratings
                    WHERE school_id IN ({placeholders})
                    GROUP BY school_id""",
                unique,
            ).fetchall()
        by_id = {
            row["school_id"]: self._summary_from_row(row["school_id"], row)
            for row in rows
        }
        return self._with_reviews({
            school_id: by_id.get(school_id, self._empty_summary(school_id))
            for school_id in unique
        })
