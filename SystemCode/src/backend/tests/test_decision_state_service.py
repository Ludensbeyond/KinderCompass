import unittest

from SystemCode.src.backend.services.decision_state_service import enrich_decision_state


class DecisionStateServiceTests(unittest.TestCase):
    def test_records_preference_change_without_turn_text(self) -> None:
        before = {
            "hard_constraints": {"language": "Chinese"},
            "preferences": {},
            "decision_state": {"recent_topics": ["update_preferences"]},
        }
        result = {
            "profile": {"hard_constraints": {}, "preferences": {}},
            "status": "ready_to_search",
            "question": "Raw assistant text must not enter decision state",
        }

        enriched = enrich_decision_state(before, result, intent="update_preferences")
        state = enriched["profile"]["decision_state"]

        self.assertEqual(state["recent_decisions"][0]["attribute"], "language")
        self.assertEqual(state["recent_decisions"][0]["from"], "Chinese")
        self.assertNotIn("question", state)
        self.assertNotIn("message", state)

    def test_prioritises_pending_decision_as_current_goal(self) -> None:
        result = {
            "profile": {
                "hard_constraints": {}, "preferences": {},
                "pending_contradiction": {"attribute": "language"},
            },
            "status": "needs_clarification",
        }
        state = enrich_decision_state({}, result, intent="update_preferences")["profile"]["decision_state"]
        self.assertEqual(state["current_goal"], "contradiction")
        self.assertEqual(
            state["unresolved_questions"],
            [{"kind": "contradiction", "attribute": "language"}],
        )

    def test_does_not_duplicate_legacy_and_canonical_preference_change(self) -> None:
        result = {
            "profile": {
                "hard_constraints": {"language": "Chinese"},
                "preferences": {},
                "preference_items": [
                    {"attribute": "language", "value": "Chinese", "importance": "required"}
                ],
            },
            "status": "ready_to_search",
        }
        decisions = enrich_decision_state({}, result, intent="update_preferences")["profile"]["decision_state"]["recent_decisions"]
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["attribute"], "language")

    def test_bounds_middle_context(self) -> None:
        before = {
            "hard_constraints": {}, "preferences": {},
            "decision_state": {
                "recent_topics": [f"topic-{index}" for index in range(20)],
                "recent_decisions": [
                    {"attribute": f"item-{index}", "from": None, "to": True}
                    for index in range(20)
                ],
            },
        }
        result = {"profile": {"hard_constraints": {}, "preferences": {}}, "status": "comparison"}
        state = enrich_decision_state(before, result, intent="comparison")["profile"]["decision_state"]
        self.assertEqual(len(state["recent_topics"]), 6)
        self.assertEqual(len(state["recent_decisions"]), 8)
        self.assertEqual(state["recent_topics"][-1], "comparison")


if __name__ == "__main__":
    unittest.main()
