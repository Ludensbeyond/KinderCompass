from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Iterator

from SystemCode.src.backend.domain.catalogue import EvaluatedSchool
from SystemCode.src.backend.domain.models import FeedbackRequest


class FeedbackSnapshotNotFoundError(LookupError):
    pass


class FeedbackSchoolMismatchError(ValueError):
    pass


class FeedbackService:
    """Persist privacy-minimised recommendation snapshots and consented feedback."""

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
                CREATE TABLE IF NOT EXISTS recommendation_snapshots (
                    trace_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    catalogue_version TEXT NOT NULL,
                    ranking_method TEXT NOT NULL,
                    recommendations_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS feedback_events (
                    event_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    anonymous_session_id TEXT NOT NULL,
                    school_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    reason TEXT,
                    rating INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(trace_id) REFERENCES recommendation_snapshots(trace_id)
                );
            """)

    def record_snapshot(
        self,
        trace_id: str | None,
        centres: list[EvaluatedSchool],
        *,
        catalogue_version: str,
    ) -> None:
        if not trace_id:
            return
        recommendations = [
            {
                "school_id": centre.school_id,
                "rank": index,
                "match_score": centre.get("match_score"),
                "profile_confidence": centre.get("profile_confidence"),
                "programme_id": centre.programme_id,
                "net_monthly_fee": centre.net_monthly_fee,
                "policy_id": (
                    centre.policy_source.policy_id if centre.policy_source else None
                ),
            }
            for index, centre in enumerate(centres, start=1)
        ]
        serialized = json.dumps(recommendations, sort_keys=True, separators=(",", ":"))
        with self._connect() as connection:
            existing = connection.execute(
                """SELECT catalogue_version, ranking_method, recommendations_json
                   FROM recommendation_snapshots WHERE trace_id = ?""",
                (trace_id,),
            ).fetchone()
            if existing:
                if (
                    existing["recommendations_json"] != serialized
                    or existing["catalogue_version"] != catalogue_version
                    or existing["ranking_method"]
                    != "verified_match_then_evidence_confidence"
                ):
                    raise ValueError("A different recommendation snapshot already uses this trace ID")
                return
            connection.execute(
                """INSERT INTO recommendation_snapshots
                   (trace_id, created_at, catalogue_version, ranking_method, recommendations_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    trace_id,
                    datetime.now(timezone.utc).isoformat(),
                    catalogue_version,
                    "verified_match_then_evidence_confidence",
                    serialized,
                ),
            )

    def record_feedback(self, request: FeedbackRequest) -> str:
        with self._connect() as connection:
            snapshot = connection.execute(
                "SELECT recommendations_json FROM recommendation_snapshots WHERE trace_id = ?",
                (str(request.trace_id),),
            ).fetchone()
            if snapshot is None:
                raise FeedbackSnapshotNotFoundError("Recommendation snapshot was not found")
            school_ids = {
                item["school_id"] for item in json.loads(snapshot["recommendations_json"])
            }
            if request.school_id not in school_ids:
                raise FeedbackSchoolMismatchError(
                    "Feedback school is not part of this recommendation snapshot"
                )
            event_id = str(uuid.uuid4())
            connection.execute(
                """INSERT INTO feedback_events
                   (event_id, trace_id, anonymous_session_id, school_id, event_type,
                    reason, rating, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_id,
                    str(request.trace_id),
                    str(request.anonymous_session_id),
                    request.school_id,
                    request.event_type,
                    request.reason,
                    request.rating,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return event_id
