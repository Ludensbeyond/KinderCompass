import os
import unittest
from unittest.mock import patch

from stage1.conversation import update_conversation
from stage1.intent_router import IntentResult, TopicEntity, classify_intent
from stage1.web_rag import retrieve_general_evidence


GENERAL_INDEX = {
    "chunks": [
        {
            "chunk_id": "GENERAL:play:0", "topic": "play-based learning",
            "text": "Play-based learning uses active, hands-on experiences to support development.",
            "source_url": "https://authority.example/play", "title": "Play guidance",
            "authority": "Education Authority", "retrieved_at": "2026-08-14",
        },
        {
            "chunk_id": "GENERAL:montessori:0", "topic": "Montessori",
            "text": "Montessori uses a prepared environment and self-directed activity.",
            "source_url": "https://authority.example/montessori", "title": "Montessori guidance",
            "authority": "Montessori Authority", "retrieved_at": "2026-08-14",
        },
        {
            "chunk_id": "GENERAL:reggio:0", "topic": "Reggio Emilia",
            "text": "Reggio Emilia values relationships, expression and documentation.",
            "source_url": "https://authority.example/reggio", "title": "Reggio guidance",
            "authority": "Reggio Authority", "retrieved_at": "2026-08-14",
        },
        {
            "chunk_id": "GENERAL:spark:0", "topic": "SPARK 2.0",
            "text": "SPARK 2.0 is Singapore's preschool quality-improvement framework.",
            "source_url": "https://authority.example/spark", "title": "SPARK guidance",
            "authority": "ECDA", "retrieved_at": "2026-08-14",
        },
        {
            "chunk_id": "GENERAL:subsidy:0", "topic": "Basic Subsidy and Additional Subsidy",
            "text": "Basic Subsidy supports eligible Singapore Citizen children. Additional Subsidy is means-tested.",
            "source_url": "https://authority.example/subsidy", "title": "Subsidy guidance",
            "authority": "ECDA", "retrieved_at": "2026-08-14",
        },
    ]
}

SCHOOL_INDEX = {
    "pages": [{
        "school_id": "S1", "chunks": [{
            "chunk_id": "S1:0", "school_id": "S1",
            "text": "Our preschool uses play-based learning in daily classroom activities.",
            "source_url": "https://school.example/programme", "title": "School programme",
            "retrieved_at": "2026-08-14",
        }],
    }]
}


class GeneralKnowledgeRagTests(unittest.TestCase):
    def test_routes_general_curriculum_question_without_selected_school(self):
        self.assertEqual(classify_intent("What is Montessori?").intent, "ask_general_knowledge")
        turn = update_conversation(None, "What is Montessori?", general_knowledge_index=GENERAL_INDEX)
        self.assertEqual(turn["status"], "general_knowledge")
        self.assertFalse(turn["ranking_affected"])
        self.assertEqual(turn["citations"][0]["evidence_scope"], "general")
        self.assertNotIn("school_id", turn["citations"][0])

    def test_general_retrieval_carries_authority_and_scope(self):
        result = retrieve_general_evidence(GENERAL_INDEX, "Explain play-based learning", limit=1)[0]
        self.assertEqual(result["evidence_scope"], "general")
        self.assertEqual(result["citation"]["authority"], "Education Authority")

    def test_comparison_returns_both_general_sources(self):
        turn = update_conversation(
            None, "What is the difference between Montessori and Reggio Emilia?",
            general_knowledge_index=GENERAL_INDEX,
        )
        self.assertEqual(len(turn["citations"]), 2)
        self.assertIn("Montessori", turn["question"])
        self.assertIn("Reggio Emilia", turn["question"])

    def test_montessori_and_spark_are_explained_as_different_concepts(self):
        turn = update_conversation(
            None, "Whats the difference between Montessori and Spark?",
            general_knowledge_index=GENERAL_INDEX,
        )
        self.assertEqual(turn["status"], "general_knowledge")
        self.assertFalse(turn["ranking_affected"])
        self.assertEqual(len(turn["citations"]), 2)
        self.assertEqual(
            {citation["chunk_id"] for citation in turn["citations"]},
            {"GENERAL:montessori:0", "GENERAL:spark:0"},
        )
        self.assertIn("not direct alternatives", turn["question"])
        self.assertIn("educational approach", turn["question"])
        self.assertIn("quality-improvement framework", turn["question"])

    def test_llm_semantics_take_priority_for_mixed_general_topics(self):
        classified = IntentResult(
            intent="ask_general_knowledge",
            confidence=0.98,
            method="llm",
            topics=[
                TopicEntity(name="Montessori", category="pedagogy"),
                TopicEntity(name="SPARK 2.0", category="quality_framework"),
            ],
            relationship="different_categories",
        )
        with patch.dict(os.environ, {"OPENAI_INTENT_CLASSIFICATION_ENABLED": "true"}), patch(
            "stage1.intent_router._classify_with_openai", return_value=classified
        ) as mocked_llm:
            turn = update_conversation(
                None,
                "How should I compare Montessori with SPARK?",
                general_knowledge_index=GENERAL_INDEX,
            )
        mocked_llm.assert_called_once()
        self.assertEqual(turn["profile"]["intent_method"], "llm")
        self.assertEqual(len(turn["citations"]), 2)
        self.assertIn("not direct alternatives", turn["question"])
        self.assertIn("educational approach", turn["question"])
        self.assertIn("quality-improvement framework", turn["question"])

    def test_combined_answer_keeps_school_and_general_sources_distinct(self):
        selected = [{"school_id": "S1", "name": "Example Preschool"}]
        turn = update_conversation(
            None, "This school uses play-based learning. What does that mean?", selected,
            web_rag_index=SCHOOL_INDEX, general_knowledge_index=GENERAL_INDEX,
        )
        self.assertEqual(turn["status"], "combined_evidence")
        self.assertEqual({item["evidence_scope"] for item in turn["citations"]}, {"school", "general"})
        self.assertFalse(turn["ranking_affected"])

    def test_subsidy_question_routes_to_dated_general_guidance(self):
        turn = update_conversation(
            None, "How much is the Basic Subsidy and Additional Subsidy?",
            general_knowledge_index=GENERAL_INDEX,
        )
        self.assertEqual(turn["status"], "general_knowledge")
        self.assertEqual(turn["citations"][0]["authority"], "ECDA")
        self.assertEqual(turn["evidence_category"], "authoritative_fact")
        self.assertFalse(turn["ranking_affected"])


if __name__ == "__main__":
    unittest.main()
