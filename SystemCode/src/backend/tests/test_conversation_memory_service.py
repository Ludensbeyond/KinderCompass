import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from SystemCode.src.backend.services.conversation_memory_service import ConversationMemoryService


class ConversationMemoryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / "memory.sqlite3"
        self.service = ConversationMemoryService(self.database)
        self.session_id = uuid.uuid4()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_round_trip_keeps_only_structured_preferences(self) -> None:
        self.service.save(self.session_id, {
            "hard_constraints": {"language": "Mandarin"},
            "preferences": {"pedagogy": "Montessori"},
            "preference_items": [],
            "recognized": ["Mandarin"],
            "answered_facets": ["language"],
            "decision_state": {"current_goal": "optional_clarification"},
            "pending_contradiction": {"attribute": "language"},
            "active_school": {"school_id": "secret-selection"},
            "raw_chat": "My child and income details",
        })

        restored = self.service.restore(self.session_id)

        self.assertEqual(restored["hard_constraints"], {"language": "Mandarin"})
        self.assertEqual(restored["answered_facets"], ["language"])
        self.assertEqual(restored["decision_state"]["current_goal"], "optional_clarification")
        self.assertEqual(restored["pending_contradiction"]["attribute"], "language")
        self.assertNotIn("raw_chat", restored)
        self.assertNotIn("active_school", restored)

    def test_forget_removes_saved_profile(self) -> None:
        self.service.save(self.session_id, {"hard_constraints": {}, "preferences": {}})
        self.service.forget(self.session_id)
        self.assertIsNone(self.service.restore(self.session_id))

    def test_expired_profile_is_removed(self) -> None:
        self.service.save(self.session_id, {"hard_constraints": {}, "preferences": {}})
        expired = (datetime.now(timezone.utc) - timedelta(days=181)).isoformat()
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("UPDATE conversation_memory SET updated_at = ?", (expired,))
            connection.commit()
        self.assertIsNone(self.service.restore(self.session_id))


if __name__ == "__main__":
    unittest.main()
