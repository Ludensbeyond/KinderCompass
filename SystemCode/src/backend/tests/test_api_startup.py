import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from SystemCode.src.backend import main


class ApiStartupTests(unittest.TestCase):
    def test_backend_resolves_repository_paths_after_import(self) -> None:
        expected_root = Path(__file__).resolve().parents[4]
        self.assertEqual(main.REPO_ROOT, expected_root)
        self.assertTrue(main.POC_SRC.is_dir())
        self.assertEqual(main.health(), {"status": "ok"})

    @patch.object(main.LOCATION_SERVICE, "attach_distances")
    @patch.object(main.SCHOOL_REPOSITORY, "get_many")
    @patch.object(main.SCHOOL_REPOSITORY, "all")
    @patch("SystemCode.src.backend.services.preference_service.classify_intent")
    def test_nearest_chat_uses_postal_code_and_full_grounded_catalogue(
        self, mock_intent, mock_all, mock_get_many, mock_distances
    ) -> None:
        from stage1.intent_router import IntentResult

        mock_intent.return_value = IntentResult(intent="find_closest_preschool", confidence=0.99, method="llm")
        mock_all.return_value = [
            {"school_id": "A", "centre_code": "A", "name": "Far School"},
            {"school_id": "B", "centre_code": "B", "name": "Near School"},
        ]
        mock_distances.return_value = [
            {"school_id": "A", "centre_code": "A", "name": "Far School", "distance_km": 1.2},
            {"school_id": "B", "centre_code": "B", "name": "Near School", "distance_km": 0.3},
        ]
        mock_get_many.return_value = [mock_distances.return_value[1]]

        response = TestClient(main.app).post("/api/preferences", json={
            "message": "Which is the nearest school?",
            "home_postal_code": "540231",
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn("Near School", response.json()["question"])
        self.assertIn("0.30 km", response.json()["question"])
        self.assertEqual(response.json()["profile"]["active_school"]["school_id"], "B")
        self.assertEqual(response.json()["evidence_category"], "calculated_estimate")
        mock_all.assert_called_once_with()
        mock_distances.assert_any_call(mock_all.return_value, "540231")

        mock_intent.return_value = IntentResult(intent="ask_selected_school_evidence", confidence=0.99, method="llm")
        follow_up = TestClient(main.app).post("/api/preferences", json={
            "message": "What type of education does it have?",
            "profile": response.json()["profile"],
            "home_postal_code": "540231",
        })

        self.assertEqual(follow_up.status_code, 200)
        self.assertNotIn("Select one preschool", follow_up.json()["question"])
        self.assertIn(follow_up.json()["evidence_category"], {"school_published_claim", "unknown"})


if __name__ == "__main__":
    unittest.main()
