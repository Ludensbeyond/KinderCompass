import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline import search_and_evaluate
from stage1.query_builder import build_stage1_query
from stage1.nlp_mapper import map_text_to_filters, merge_preference_profile, summarize_profile
from stage1.scorer import rank_schools, score_school
from stage1.conversation import update_conversation
from stage1.preference_schema import make_preference_item, validate_preference_profile
from stage1.llm_extractor import ExtractedPreference, ExtractionResult
from stage1.grounded_explainer import (
    GroundedExplanation,
    WebEvidenceAnswer,
    _focused_web_passage,
    web_rag_answers_enabled,
)
from stage1.intent_router import IntentResult, classify_intent
from stage1.proximity import filter_within_radius
from stage1 import proximity
from stage2.engine import evaluate_preschool_eligibility, evaluate_shortlist
from stage2.runner import run_from_file
from scripts.evaluate_recommendations import evaluate
from scripts.evaluate_web_rag_answers import evaluate as evaluate_web_answers, _expected_term_matches
from scripts.audit_evidence_quality import audit as audit_evidence_quality
from scripts.build_website_inventory import build_inventory, normalize_url
from stage1.evidence import freshness


SCHOOL = {
    "school_id": "CENTRE:ST0001",
    "centre_code": "ST0001",
    "name": "Example Preschool",
    "base_fee": 1200.0,
    "operator_scheme": "Anchor Operator Scheme",
    "care_levels": ["Pre-Nursery (3 yrs old)"],
    "pedagogy": "Play-based",
}


class Stage2Tests(unittest.TestCase):
    def test_evaluates_eligible_school(self):
        result = evaluate_preschool_eligibility(
            dob=dt.date(2023, 6, 10),
            admission_date=dt.date(2026, 6, 10),
            ghi=4500,
            base_fee=1200,
            basic_subsidy=600,
            care_levels=SCHOOL["care_levels"],
        )
        self.assertTrue(result["eligible"])
        self.assertEqual(result["eligible_level"], "Pre-Nursery (3 yrs old)")
        self.assertEqual(result["net_monthly_fee"], 160.0)

    def test_filters_school_without_required_level(self):
        school = {**SCHOOL, "care_levels": ["Kindergarten 1 (5 yrs old)"]}
        result = evaluate_shortlist(
            [school],
            dob=dt.date(2023, 6, 10),
            admission_date=dt.date(2026, 6, 10),
            ghi=4500,
            basic_subsidy=600,
        )
        self.assertEqual(result, [])

    def test_missing_fee_does_not_fail_entire_shortlist(self):
        incomplete = {
            "school_id": "TP:TP0001",
            "centre_code": "na",
            "tp_code": "TP0001",
            "name": "Incomplete Preschool",
            "base_fee": None,
        }
        result = evaluate_shortlist(
            [incomplete, SCHOOL],
            dob=dt.date(2023, 6, 10),
            admission_date=dt.date(2026, 6, 10),
            ghi=4500,
            basic_subsidy=600,
        )
        self.assertEqual([school["school_id"] for school in result], [SCHOOL["school_id"]])

    def test_missing_fee_can_be_returned_with_quality_reason(self):
        incomplete = {
            "school_id": "TP:TP0001",
            "centre_code": "na",
            "base_fee": None,
        }
        result = evaluate_shortlist(
            [incomplete],
            dob=dt.date(2023, 6, 10),
            admission_date=dt.date(2026, 6, 10),
            ghi=4500,
            basic_subsidy=600,
            include_ineligible=True,
        )
        self.assertFalse(result[0]["eligible"])
        self.assertIn("unavailable", result[0]["reason"])


class PipelineTests(unittest.TestCase):
    def test_web_rag_llm_defaults_to_enabled_outside_agent_mode(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(web_rag_answers_enabled())

    def test_web_rag_llm_can_be_explicitly_disabled(self):
        with patch.dict(os.environ, {"OPENAI_WEB_RAG_ANSWERS_ENABLED": "false"}, clear=True):
            self.assertFalse(web_rag_answers_enabled())

    def test_agent_mode_disables_legacy_web_rag_llm(self):
        with patch.dict(os.environ, {"WEB_RAG_ANSWER_MODE": "agent"}, clear=True):
            self.assertFalse(web_rag_answers_enabled())

    def test_phase9_answer_evaluator_normalises_dotted_acronyms(self):
        self.assertTrue(_expected_term_matches("An immersive S.T.E.A.M. curriculum.", "STEAM"))

    def test_phase9_llm_context_focuses_on_named_language_evidence(self):
        text = " ".join(["generic"] * 80) + " English and Chinese are taught through bilingual activities."
        focused = _focused_web_passage("What languages are taught in this school?", text)
        self.assertIn("English and Chinese", focused)
        self.assertLess(len(focused.split()), len(text.split()))

    def test_phase9_llm_context_focuses_on_fee_amounts(self):
        text = "Welcome and programme details. Full Day: $880 Half Day: $595 Maximum Possible Subsidies apply."
        focused = _focused_web_passage("How much are this school's fees and subsidies?", text)
        self.assertIn("$880", focused)
        self.assertIn("$595", focused)

    def test_phase9_answer_quality_evaluator_checks_grounding(self):
        index = {"pages": [{"school_id": "A", "chunks": [{
            "chunk_id": "A:1", "school_id": "A",
            "text": "The preschool uses a literature-based curriculum for children.",
            "source_url": "https://a.example", "title": "School A",
            "retrieved_at": "2026-08-10", "content_hash": "a",
        }]}]}
        labels = {"cases": [{
            "case_id": "curriculum", "school_id": "A", "school_name": "School A",
            "question": "What curriculum does this school use?", "evidence_expected": True,
            "expected_terms": ["literature-based"], "forbidden_terms": ["montessori"],
        }]}
        report = evaluate_web_answers(index, labels, thresholds={"minimum_cases": 1})
        self.assertTrue(report["passed"])
        self.assertEqual(report["metrics"]["citation_validity"], 1.0)
        self.assertEqual(report["metrics"]["unsupported_claim_free_rate"], 1.0)

    def test_one_km_distance_is_numeric_not_boolean(self):
        item = make_preference_item("max_distance_km", 1.0, "required")
        self.assertEqual(item["value"], 1.0)

    def test_exact_rag_search_preference_does_not_crash(self):
        turn = update_conversation(
            None, "I prefer Chinese, SPARK certification, and full-day care within 1 km."
        )
        self.assertEqual(turn["profile"]["hard_constraints"]["max_distance_km"], 1.0)

    def test_phase9_selected_school_question_returns_isolated_citations(self):
        index = {"purpose": "explanation_only", "pages": [
            {"school_id": "A", "chunks": [{
                "chunk_id": "A:1", "school_id": "A",
                "text": "Children learn through a literature-based and activity-based curriculum.",
                "source_url": "https://a.example/curriculum", "title": "School A curriculum",
                "retrieved_at": "2026-08-10", "content_hash": "a",
            }]},
            {"school_id": "B", "chunks": [{
                "chunk_id": "B:1", "school_id": "B", "text": "A Montessori curriculum.",
                "source_url": "https://b.example", "title": "School B",
                "retrieved_at": "2026-08-10", "content_hash": "b",
            }]},
        ], "operator_pages": []}
        turn = update_conversation(
            None, "What curriculum does this school use?",
            [{"school_id": "A", "name": "School A"}], web_rag_index=index,
        )
        self.assertEqual(turn["status"], "web_evidence")
        self.assertIn("literature-based", turn["question"])
        self.assertNotIn("Montessori", turn["question"])
        self.assertEqual(turn["citations"][0]["url"], "https://a.example/curriculum")
        self.assertEqual(turn["evidence_scope"], "school")
        self.assertFalse(turn["ranking_affected"])

    def test_phase9_web_answer_summarises_noisy_chunks(self):
        index = {"pages": [{"school_id": "A", "chunks": [{
            "chunk_id": "A:1", "school_id": "A",
            "text": (
                "Experience this centre Awards and navigation labels before the useful evidence "
                "A common outdoor playground outside the centre supports outdoor learning "
                "Age group links partners-partneroperator _DSC4863 How to reach us and more navigation labels"
            ),
            "source_url": "https://a.example", "title": "School A",
            "retrieved_at": "2026-08-10", "content_hash": "a",
        }]}]}
        turn = update_conversation(
            None, "Does this school provide outdoor learning?",
            [{"school_id": "A", "name": "School A"}], web_rag_index=index,
        )
        self.assertIn("outdoor playground", turn["question"])
        self.assertLess(len(turn["question"]), 500)
        self.assertNotIn("_DSC4863", turn["question"])
        self.assertEqual(len(turn["citations"]), 1)

    def test_phase9_llm_synthesises_only_retrieved_web_evidence(self):
        index = {"pages": [{"school_id": "A", "chunks": [{
            "chunk_id": "A:1", "school_id": "A", "text": "A literature-based curriculum.",
            "source_url": "https://a.example", "title": "School A",
            "retrieved_at": "2026-08-10", "content_hash": "a",
        }]}]}
        generated = WebEvidenceAnswer(
            answer="The preschool uses a literature-based curriculum.",
            citation_ids=["A:1"], evidence_available=True,
        )
        with patch.dict(os.environ, {"OPENAI_WEB_RAG_ANSWERS_ENABLED": "true"}), patch(
            "stage1.grounded_explainer._answer_web_evidence_with_openai", return_value=generated
        ):
            turn = update_conversation(
                None, "What curriculum does this school use?",
                [{"school_id": "A", "name": "School A"}], web_rag_index=index,
            )
        self.assertEqual(turn["question"], generated.answer)
        self.assertEqual(turn["citations"][0]["chunk_id"], "A:1")
        self.assertEqual(turn["web_answer_method"], "llm_grounded")

    def test_phase9_llm_invalid_citation_uses_deterministic_fallback(self):
        index = {"pages": [{"school_id": "A", "chunks": [{
            "chunk_id": "A:1", "school_id": "A", "text": "A literature-based curriculum.",
            "source_url": "https://a.example", "title": "School A",
            "retrieved_at": "2026-08-10", "content_hash": "a",
        }]}]}
        invalid = WebEvidenceAnswer(
            answer="An unsupported answer.", citation_ids=["B:1"], evidence_available=True,
        )
        with patch.dict(os.environ, {"OPENAI_WEB_RAG_ANSWERS_ENABLED": "true"}), patch(
            "stage1.grounded_explainer._answer_web_evidence_with_openai", return_value=invalid
        ):
            turn = update_conversation(
                None, "What curriculum does this school use?",
                [{"school_id": "A", "name": "School A"}], web_rag_index=index,
            )
        self.assertIn("relevant page", turn["question"])
        self.assertEqual(turn["web_answer_method"], "deterministic_fallback")
        self.assertEqual(turn["web_answer_fallback_reason"], "ValueError")

    def test_phase9_llm_cannot_reject_retrieved_evidence(self):
        index = {"pages": [{"school_id": "A", "chunks": [{
            "chunk_id": "A:1", "school_id": "A", "text": "English Speech and Drama is available.",
            "source_url": "https://a.example", "title": "School A",
            "retrieved_at": "2026-08-10", "content_hash": "a",
        }]}]}
        rejected = WebEvidenceAnswer(
            answer="Evidence is unavailable.", citation_ids=[], evidence_available=False,
        )
        with patch.dict(os.environ, {"OPENAI_WEB_RAG_ANSWERS_ENABLED": "true"}), patch(
            "stage1.grounded_explainer._answer_web_evidence_with_openai", return_value=rejected
        ):
            turn = update_conversation(
                None, "What languages are taught in this school?",
                [{"school_id": "A", "name": "School A"}], web_rag_index=index,
            )
        self.assertEqual(turn["web_answer_method"], "deterministic_fallback")
        self.assertIn("English", turn["question"])
        self.assertEqual(turn["citations"][0]["chunk_id"], "A:1")

    def test_phase9_selected_school_question_reports_unavailable_evidence(self):
        turn = update_conversation(
            None, "Does this school have an outdoor playground?",
            [{"school_id": "A", "name": "School A"}], web_rag_index={"pages": []},
        )
        self.assertEqual(turn["citations"], [])
        self.assertEqual(turn["evidence_scope"], "unavailable")
        self.assertIn("unavailable, not that the answer is no", turn["question"])

    def test_phase9_web_evidence_requires_exactly_one_selected_school(self):
        turn = update_conversation(
            None, "What curriculum does this school use?",
            [{"school_id": "A"}, {"school_id": "B"}], web_rag_index={"pages": []},
        )
        self.assertIn("Select only one", turn["question"])
        self.assertEqual(turn["citations"], [])

    def test_phase9_normalizes_webpage_candidates(self):
        url, error = normalize_url("www.example.edu.sg/curriculum/?utm_source=test#section")
        self.assertIsNone(error)
        self.assertEqual(url, "https://www.example.edu.sg/curriculum")

    def test_phase9_classifies_shared_and_unique_candidate_pages(self):
        report = build_inventory([
            {"school_id": "A", "centre_name_x": "A", "centre_website": "operator.sg/preschools"},
            {"school_id": "B", "centre_name_x": "B", "website_lifesg": "https://operator.sg/preschools/"},
            {"school_id": "C", "centre_name_x": "C", "centre_website": "school-c.sg/about"},
            {"school_id": "D", "centre_name_x": "D"},
        ])
        by_id = {item["school_id"]: item for item in report["schools"]}
        self.assertEqual(by_id["A"]["scope"], "shared_operator_page_candidate")
        self.assertEqual(by_id["B"]["schools_sharing_selected_url"], 2)
        self.assertEqual(by_id["C"]["scope"], "school_specific_candidate")
        self.assertEqual(by_id["D"]["scope"], "unavailable")
        self.assertTrue(all(item["identity_status"] != "verified" for item in report["schools"]))

    def test_phase8_stage1_query_returns_source_update_date(self):
        query, _ = build_stage1_query(map_text_to_filters("SPARK"))
        self.assertIn("p.last_updated AS last_updated", query)

    def test_phase8_distinguishes_confirmed_no_from_unknown(self):
        profile = map_text_to_filters("SPARK")
        confirmed_no = score_school(profile, {**SCHOOL, "spark_certified": "No", "last_updated": "2026-01-01"})
        unknown = score_school(profile, {**SCHOOL, "spark_certified": None})
        self.assertEqual(confirmed_no["match_breakdown"][0]["value_state"], "confirmed_no")
        self.assertEqual(confirmed_no["match_breakdown"][0]["evidence_state"], "verified")
        self.assertEqual(unknown["match_breakdown"][0]["value_state"], "unknown")
        self.assertEqual(unknown["match_breakdown"][0]["evidence_state"], "unknown")

    def test_phase8_marks_pedagogy_as_derived(self):
        profile = map_text_to_filters("Montessori")
        scored = score_school(profile, {**SCHOOL, "pedagogy": "Montessori", "last_updated": "2026-01-01"})
        evidence = scored["match_breakdown"][0]
        self.assertEqual(evidence["source_method"], "derived_from_centre_name")
        self.assertEqual(evidence["source_reliability"], "limited")
        self.assertEqual(evidence["evidence_state"], "derived")

    def test_phase8_freshness_classification(self):
        today = dt.date(2026, 8, 10)
        self.assertEqual(freshness("2026-07-17", today), "current")
        self.assertEqual(freshness("2024-01-01", today), "stale")
        self.assertEqual(freshness(None, today), "unknown")

    def test_phase8_evidence_audit_reports_value_states(self):
        report = audit_evidence_quality([
            {"spark_certified": "No", "pedagogy": "Montessori", "last_updated": "2026-07-17"},
            {"spark_certified": None, "pedagogy": None, "last_updated": None},
        ])
        spark = next(item for item in report["fields"] if item["attribute"] == "spark_certified")
        pedagogy = next(item for item in report["fields"] if item["attribute"] == "pedagogy")
        self.assertEqual(spark["confirmed_no"], 1)
        self.assertEqual(spark["unknown"], 1)
        self.assertEqual(pedagogy["derived"], 1)
        self.assertEqual(report["invalid_provenance_attributes"], [])

    def test_phase8_chat_explains_selected_school_sources(self):
        selected = [{
            "school_id": "A", "name": "School A",
            "match_breakdown": [{
                "attribute": "pedagogy", "evidence_state": "derived",
                "source": "KinderCompass derivation", "source_reliability": "limited",
                "freshness": "current",
            }],
        }]
        turn = update_conversation(None, "Where did this school information come from?", selected)
        self.assertIn("KinderCompass derivation", turn["question"])
        self.assertIn("limited reliability", turn["question"])

    def test_phase7_golden_recommendation_scenarios_pass(self):
        report = evaluate()
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertEqual(report["summary"]["total"], 5)
        self.assertIn("Synthetic fixtures only", report["privacy"])

    def test_phase5_explains_why_first_school_is_top_ranked(self):
        eligible = [
            {"school_id": "A", "name": "School A", "match_score": 92, "profile_confidence": 0.8, "strengths": ["pedagogy", "language"], "tradeoffs": ["transport"]},
            {"school_id": "B", "name": "School B", "match_score": 80, "profile_confidence": 1.0},
        ]
        turn = update_conversation(None, "Why is this preschool ranked first?", [], eligible)
        self.assertIn("School A is ranked first", turn["question"])
        self.assertIn("92% preference match", turn["question"])
        self.assertIn("cost and distance do not change this ranking", turn["question"])

    def test_phase5_compares_all_selected_preschools(self):
        selected = [
            {"school_id": "A", "name": "School A", "match_score": 90, "net_monthly_fee": 500, "distance_km": 1.2, "strengths": ["language"]},
            {"school_id": "B", "name": "School B", "match_score": 75, "net_monthly_fee": 350, "distance_km": 0.7, "tradeoffs": ["spark certified"]},
        ]
        turn = update_conversation(None, "Compare the selected preschools", selected)
        self.assertIn("School A", turn["question"])
        self.assertIn("School B", turn["question"])
        self.assertIn("$500/month", turn["question"])
        self.assertIn("0.70 km", turn["question"])

    def test_phase5_explains_selected_tradeoffs(self):
        selected = [{"school_id": "A", "name": "School A", "tradeoffs": ["transport", "language"]}]
        turn = update_conversation(None, "What are the trade-offs?", selected)
        self.assertIn("School A", turn["question"])
        self.assertIn("transport, language", turn["question"])

    def test_phase5_grounded_comparison_must_reference_every_school(self):
        selected = [
            {"school_id": "A", "name": "School A", "match_score": 90},
            {"school_id": "B", "name": "School B", "match_score": 80},
        ]
        incomplete = GroundedExplanation(answer="School A scores higher.", referenced_school_ids=["A"])
        with patch.dict(os.environ, {"OPENAI_GROUNDED_EXPLANATIONS_ENABLED": "true"}), patch(
            "stage1.grounded_explainer._explain_with_openai", return_value=incomplete
        ):
            turn = update_conversation(None, "Compare the selected preschools", selected)
        self.assertEqual(turn["profile"]["explanation_method"], "deterministic_fallback")
        self.assertIn("School B", turn["question"])

    def test_stage1_chat_finds_closest_from_all_eligible_preschools(self):
        eligible = [
            {"name": "School A", "distance_km": 1.2},
            {"name": "School B", "distance_km": 0.45},
            {"name": "School C", "distance_km": 2.1},
        ]
        turn = update_conversation(
            None,
            "Which of the preschool is closest to my location?",
            [],
            eligible,
        )
        self.assertEqual(turn["status"], "comparison")
        self.assertIn("School B", turn["question"])
        self.assertIn("0.45 km", turn["question"])
        self.assertEqual(turn["profile"]["active_school"]["name"], "School B")

    def test_stage1_closest_question_is_interpreted_by_llm_first(self):
        interpreted = IntentResult(
            intent="find_closest_preschool", confidence=0.99, method="llm"
        )
        with patch.dict(os.environ, {"OPENAI_INTENT_CLASSIFICATION_ENABLED": "true"}), patch(
            "stage1.intent_router._classify_with_openai", return_value=interpreted
        ) as mocked_llm:
            result = classify_intent("What is the nearest preschool?")
        self.assertEqual(result.intent, "find_closest_preschool")
        self.assertEqual(result.method, "llm")
        mocked_llm.assert_called_once()

    def test_stage1_intent_llm_defaults_to_enabled(self):
        interpreted = IntentResult(
            intent="find_closest_preschool", confidence=0.99, method="llm"
        )
        with patch.dict(os.environ, {}, clear=True), patch(
            "stage1.intent_router._classify_with_openai", return_value=interpreted
        ) as mocked_llm:
            result = classify_intent("What is the nearest preschool?")
        self.assertEqual(result.method, "llm")
        mocked_llm.assert_called_once()

    def test_stage1_numeric_radius_is_a_requirement_even_when_llm_is_enabled(self):
        conflicting = IntentResult(
            intent="find_closest_preschool", confidence=0.99, method="llm"
        )
        with patch.dict(os.environ, {"OPENAI_INTENT_CLASSIFICATION_ENABLED": "true"}), patch(
            "stage1.intent_router._classify_with_openai", return_value=conflicting
        ) as mocked_llm:
            result = classify_intent("I am looking for schools within 2km from my house")
            turn = update_conversation(None, "I am looking for schools within 2km from my house")
        self.assertEqual(result.intent, "update_preferences")
        self.assertEqual(result.method, "rules")
        self.assertEqual(turn["profile"]["hard_constraints"]["max_distance_km"], 2.0)
        self.assertIn("within 2 km of your home", turn["question"])
        mocked_llm.assert_not_called()

    def test_stage1_llm_preference_statement_cannot_trigger_nearest_lookup(self):
        misrouted = IntentResult(
            intent="find_closest_preschool",
            confidence=0.99,
            method="llm",
            message_type="preference",
        )
        mock_response = type("Response", (), {"output_parsed": misrouted})()
        mock_client = type(
            "Client",
            (),
            {"responses": type("Responses", (), {"parse": lambda self, **kwargs: mock_response})()},
        )()
        with patch("openai.OpenAI", return_value=mock_client):
            result = __import__("stage1.intent_router", fromlist=["_classify_with_openai"])._classify_with_openai(
                "I want a school that teaches Chinese"
            )
        self.assertEqual(result.message_type, "preference")
        self.assertEqual(result.intent, "update_preferences")

    def test_stage1_uses_understood_preferences_after_clarification(self):
        profile = map_text_to_filters("Montessori with Chinese preferred")
        clarification = IntentResult(
            intent="needs_clarification",
            confidence=0.8,
            clarification="Could you clarify?",
            method="llm",
            message_type="unknown",
        )
        turn = update_conversation(
            profile,
            "Based on the understood preference",
            classified_intent=clarification,
        )
        self.assertTrue(turn["ready_to_search"])
        self.assertEqual(turn["status"], "ready_to_search")
        self.assertIn("Show recommendations", turn["question"])
        self.assertIn("language:Chinese", turn["profile"]["preferences"])

    def test_stage1_no_means_finish_preferences_when_profile_is_ready(self):
        profile = map_text_to_filters("Chinese preferred")
        clarification = IntentResult(
            intent="needs_clarification",
            confidence=0.8,
            clarification="Could you clarify?",
            method="llm",
            message_type="unknown",
        )
        turn = update_conversation(profile, "no", classified_intent=clarification)
        self.assertTrue(turn["ready_to_search"])
        self.assertIn("Show recommendations", turn["question"])

    def test_stage1_closest_without_grounded_candidates_requests_results(self):
        turn = update_conversation(None, "Which preschool is nearest to me?", [], [])
        self.assertIn("grounded preschool records", turn["question"])

    def test_stage1_pronoun_follow_up_uses_active_school_context(self):
        result = classify_intent("What type of education does it have?", "School B")
        self.assertEqual(result.intent, "ask_selected_school_evidence")

    def test_stage1_chat_recommends_from_selected_preschools(self):
        selected = [
            {"name": "School A", "match_score": 80, "net_monthly_fee": 500, "distance_km": 1.2},
            {"name": "School B", "match_score": 90, "net_monthly_fee": 700, "distance_km": 2.1},
        ]
        turn = update_conversation(None, "Which of the selected preschool will you recommend to me?", selected)
        self.assertEqual(turn["status"], "comparison")
        self.assertIn("School B", turn["question"])
        self.assertIn("90%", turn["question"])

    def test_stage1_comparative_wording_recommends_from_selected_schools(self):
        question = "which of the selected school is better for me?"
        selected = [
            {"name": "School A", "match_score": 80, "net_monthly_fee": 500, "distance_km": 1.2},
            {"name": "School B", "match_score": 90, "net_monthly_fee": 700, "distance_km": 2.1},
        ]

        self.assertEqual(classify_intent(question).intent, "recommend_selected_preschool")
        turn = update_conversation(None, question, selected)

        self.assertEqual(turn["status"], "comparison")
        self.assertIn("School B", turn["question"])
        self.assertNotIn("Select only one", turn["question"])

    def test_stage1_chat_requests_a_selection_before_comparing(self):
        turn = update_conversation(None, "Which of the selected preschool will you recommend to me?", [])
        self.assertIn("select at least one preschool", turn["question"])

    def test_stage1_uses_grounded_llm_explanation_for_deterministic_winner(self):
        selected = [
            {"school_id": "A", "name": "School A", "match_score": 80, "net_monthly_fee": 500, "distance_km": 1.2},
            {"school_id": "B", "name": "School B", "match_score": 90, "net_monthly_fee": 700, "distance_km": 2.1},
        ]
        grounded = GroundedExplanation(
            answer="I recommend School B because it has the stronger preference match, while School A is cheaper and closer.",
            referenced_school_ids=["B", "A"],
        )
        with patch.dict(os.environ, {"OPENAI_GROUNDED_EXPLANATIONS_ENABLED": "true"}), patch(
            "stage1.grounded_explainer._explain_with_openai", return_value=grounded
        ):
            turn = update_conversation(None, "Which of the selected preschool will you recommend to me?", selected)
        self.assertEqual(turn["profile"]["explanation_method"], "llm_grounded")
        self.assertEqual(turn["question"], grounded.answer)

    def test_stage1_rejects_grounded_explanation_referencing_unselected_school(self):
        selected = [{"school_id": "A", "name": "School A", "match_score": 80}]
        invalid = GroundedExplanation(answer="Choose School X.", referenced_school_ids=["X"])
        with patch.dict(os.environ, {"OPENAI_GROUNDED_EXPLANATIONS_ENABLED": "true"}), patch(
            "stage1.grounded_explainer._explain_with_openai", return_value=invalid
        ):
            turn = update_conversation(None, "Which of the selected preschool will you recommend to me?", selected)
        self.assertEqual(turn["profile"]["explanation_method"], "deterministic_fallback")
        self.assertEqual(turn["profile"]["explanation_fallback_reason"], "ValueError")
        self.assertIn("School A", turn["question"])

    def test_stage1_falls_back_when_grounded_explanation_times_out(self):
        selected = [{"school_id": "A", "name": "School A", "match_score": 80}]
        with patch.dict(os.environ, {"OPENAI_GROUNDED_EXPLANATIONS_ENABLED": "true"}), patch(
            "stage1.grounded_explainer._explain_with_openai", side_effect=TimeoutError
        ):
            turn = update_conversation(None, "Is the selected school suitable for me?", selected)
        self.assertEqual(turn["profile"]["explanation_method"], "deterministic_fallback")
        self.assertIn("School A", turn["question"])

    def test_stage1_chat_assesses_one_selected_school(self):
        selected = [{
            "name": "School A", "match_score": 85, "net_monthly_fee": 500,
            "distance_km": 1.2, "strengths": ["pedagogy"], "tradeoffs": ["transport"],
        }]
        turn = update_conversation(None, "Is the selected school suitable for me?", selected)
        self.assertEqual(turn["status"], "comparison")
        self.assertIn("School A appears suitable", turn["question"])
        self.assertIn("transport", turn["question"])

    def test_stage1_chat_requires_one_school_for_suitability(self):
        selected = [{"name": "School A"}, {"name": "School B"}]
        turn = update_conversation(None, "Is this school suitable for me?", selected)
        self.assertIn("selected more than one", turn["question"])

    def test_stage1_extracts_weighted_preferences_and_exact_level(self):
        profile = map_text_to_filters("Need a Montessori nursery with Chinese and SPARK")
        self.assertEqual(profile["hard_constraints"]["level"], "Nursery (4 yrs old)")
        self.assertEqual(profile["hard_constraints"]["language"], "Chinese")
        self.assertEqual(profile["preferences"]["pedagogy"]["value"], "Montessori")
        self.assertTrue(profile["preferences"]["spark_certified"]["value"])

    def test_stage1_extracts_maximum_home_distance(self):
        profile = map_text_to_filters("I am looking for a school that is less than 1.5km")
        self.assertEqual(profile["hard_constraints"]["max_distance_km"], 1.5)
        distance = next(
            item for item in profile["preference_items"]
            if item["attribute"] == "max_distance_km"
        )
        self.assertEqual(distance["importance"], "required")
        self.assertEqual(distance["evidence_class"], "partially_supported")
        self.assertIn(
            "Required distance: within 1.5 km from home", summarize_profile(profile)
        )

    def test_stage1_does_not_add_distance_when_user_does_not_mention_it(self):
        profile = map_text_to_filters("I prefer Montessori with Chinese")
        self.assertNotIn("max_distance_km", profile["hard_constraints"])
        self.assertFalse(any(
            item["attribute"] == "max_distance_km"
            for item in profile["preference_items"]
        ))

    def test_stage1_distance_preference_is_ready_to_search(self):
        turn = update_conversation(
            None, "I am looking for a school that is less than 2km"
        )
        self.assertTrue(turn["ready_to_search"])
        self.assertEqual(
            turn["profile"]["hard_constraints"]["max_distance_km"], 2.0
        )
        self.assertIn("within 2 km of your home", turn["question"])
        self.assertIn("show recommendations", turn["question"])

    def test_stage1_chat_replies_with_decimal_distance(self):
        turn = update_conversation(None, "Please find a preschool within 1.5 km")
        self.assertEqual(
            turn["question"],
            "Distance preference updated. I’ll only recommend preschools within "
            "1.5 km of your home. Add another preference or click show recommendations.",
        )

    def test_stage1_rules_preserve_distance_when_llm_misses_it(self):
        extraction = ExtractionResult(preferences=[], clarification=None)
        with patch.dict(os.environ, {"OPENAI_PREFERENCE_EXTRACTION_ENABLED": "true"}), patch(
            "stage1.llm_extractor._extract_with_openai", return_value=extraction
        ):
            turn = update_conversation(None, "I want a preschool under 3 km")
        self.assertEqual(turn["profile"]["extraction_method"], "llm")
        self.assertEqual(
            turn["profile"]["hard_constraints"]["max_distance_km"], 3.0
        )

    def test_stage1_profile_contains_valid_evidence_metadata(self):
        profile = map_text_to_filters("Need Montessori with Chinese and SPARK")
        validate_preference_profile(profile)
        self.assertEqual(profile["schema_version"], 2)
        language = next(item for item in profile["preference_items"] if item["attribute"] == "language")
        pedagogy = next(item for item in profile["preference_items"] if item["attribute"] == "pedagogy")
        self.assertEqual(language["importance"], "required")
        self.assertEqual(language["evidence_class"], "supported")
        self.assertEqual(pedagogy["evidence_class"], "partially_supported")
        self.assertIsNotNone(pedagogy["warning"])

    def test_stage1_retains_unsupported_preferences_without_ranking_them(self):
        turn = update_conversation(None, "I want hands-on learning with fewer worksheets")
        self.assertEqual(turn["status"], "unsupported_preferences")
        self.assertFalse(turn["ready_to_search"])
        self.assertEqual(len(turn["profile"]["unsupported_preferences"]), 2)
        self.assertEqual(turn["profile"]["preference_items"], [])

    def test_stage1_uses_valid_llm_extraction_when_enabled(self):
        extraction = ExtractionResult(
            preferences=[ExtractedPreference(
                attribute="language", value="Chinese", importance="preferred", confidence=0.94
            )],
            clarification=None,
        )
        with patch.dict(os.environ, {"OPENAI_PREFERENCE_EXTRACTION_ENABLED": "true"}), patch(
            "stage1.llm_extractor._extract_with_openai", return_value=extraction
        ):
            turn = update_conversation(None, "A programme where she can keep learning Mandarin would be nice")
        self.assertEqual(turn["profile"]["extraction_method"], "llm")
        self.assertIn("language:Chinese", turn["profile"]["preferences"])
        item = next(item for item in turn["profile"]["preference_items"] if item["attribute"] == "language")
        self.assertEqual(item["importance"], "preferred")
        self.assertEqual(item["confidence"], 0.94)

    def test_stage1_falls_back_when_llm_fails(self):
        with patch.dict(os.environ, {"OPENAI_PREFERENCE_EXTRACTION_ENABLED": "true"}), patch(
            "stage1.llm_extractor._extract_with_openai", side_effect=TimeoutError
        ):
            turn = update_conversation(None, "Montessori is preferred")
        self.assertEqual(turn["profile"]["extraction_method"], "rules_fallback")
        self.assertEqual(turn["profile"]["llm_fallback_reason"], "TimeoutError")
        self.assertEqual(turn["profile"]["preferences"]["pedagogy"]["value"], "Montessori")

    def test_stage1_rejects_invalid_llm_value_and_falls_back(self):
        extraction = ExtractionResult(
            preferences=[ExtractedPreference(
                attribute="language", value="Klingon", importance="preferred", confidence=0.8
            )],
            clarification=None,
        )
        with patch.dict(os.environ, {"OPENAI_PREFERENCE_EXTRACTION_ENABLED": "true"}), patch(
            "stage1.llm_extractor._extract_with_openai", return_value=extraction
        ):
            profile = update_conversation(None, "I would like an invented language")["profile"]
        self.assertEqual(profile["extraction_method"], "rules_fallback")
        self.assertEqual(profile["preferences"], {})

    def test_stage1_acknowledges_unsupported_preferences_in_existing_profile(self):
        profile = merge_preference_profile(None, "SPARK is preferred")
        turn = update_conversation(profile, "I want hands-on learning with fewer worksheets")
        self.assertEqual(turn["status"], "ready_to_search")
        self.assertTrue(turn["ready_to_search"])
        self.assertIn("cannot verify or rank", turn["question"])
        self.assertIn("hands on learning", turn["question"])
        self.assertIn("low worksheet use", turn["question"])

    def test_stage1_chat_accumulates_preferences_across_turns(self):
        profile = merge_preference_profile(None, "I prefer Montessori")
        profile = merge_preference_profile(profile, "Chinese would be preferred")
        self.assertEqual(profile["preferences"]["pedagogy"]["value"], "Montessori")
        self.assertEqual(profile["preferences"]["language:Chinese"]["value"], "Chinese")
        self.assertEqual(len(summarize_profile(profile)), 2)

    def test_stage1_chat_can_downgrade_required_language(self):
        profile = merge_preference_profile(None, "I need Chinese")
        self.assertEqual(profile["hard_constraints"]["language"], "Chinese")
        profile = merge_preference_profile(profile, "Chinese is preferred, not required")
        self.assertNotIn("language", profile["hard_constraints"])
        self.assertIn("language:Chinese", profile["preferences"])

    def test_stage1_chat_can_reset_preferences(self):
        profile = merge_preference_profile(None, "Montessori with SPARK")
        profile = merge_preference_profile(profile, "clear preferences")
        self.assertEqual(profile["hard_constraints"], {})
        self.assertEqual(profile["preferences"], {})

    def test_stage1_chat_asks_language_follow_up(self):
        turn = update_conversation(None, "I want Chinese")
        self.assertEqual(turn["status"], "needs_clarification")
        self.assertFalse(turn["ready_to_search"])
        self.assertIn("required or merely preferred", turn["question"])
        resolved = update_conversation(turn["profile"], "It is preferred")
        self.assertTrue(resolved["ready_to_search"])
        self.assertIn("language:Chinese", resolved["profile"]["preferences"])

    def test_stage1_chat_explicit_preference_is_ready(self):
        turn = update_conversation(None, "Montessori is preferred")
        self.assertEqual(turn["status"], "ready_to_search")
        self.assertTrue(turn["ready_to_search"])

    def test_stage1_chat_queues_multiple_follow_ups(self):
        turn = update_conversation(None, "Montessori with Chinese")
        first_value = turn["profile"]["pending"]["value"]
        turn = update_conversation(turn["profile"], "It is preferred")
        self.assertFalse(turn["ready_to_search"])
        self.assertNotEqual(turn["profile"]["pending"]["value"], first_value)
        turn = update_conversation(turn["profile"], "It is preferred")
        self.assertTrue(turn["ready_to_search"])

    def test_stage1_ranks_matching_school_first_with_explanation(self):
        profile = map_text_to_filters("Montessori with SPARK")
        next(item for item in profile["preference_items"] if item["attribute"] == "pedagogy")["importance"] = "preferred"
        matching = {**SCHOOL, "pedagogy": "Montessori", "spark_certified": "Yes"}
        tradeoff = {**SCHOOL, "school_id": "CENTRE:ST0002", "pedagogy": "Play-based", "spark_certified": "No"}
        ranked = rank_schools(profile, [tradeoff, matching])
        self.assertEqual(ranked[0]["school_id"], SCHOOL["school_id"])
        self.assertGreater(ranked[0]["match_score"], ranked[1]["match_score"])
        self.assertIn("pedagogy", ranked[0]["strengths"])
        self.assertIn("spark certified", ranked[1]["tradeoffs"])

    def test_stage1_missing_evidence_reduces_confidence(self):
        profile = map_text_to_filters("SPARK")
        scored = score_school(profile, SCHOOL)
        self.assertEqual(scored["match_score"], 0.0)
        self.assertEqual(scored["profile_confidence"], 0.0)
        self.assertEqual(scored["match_breakdown"][0]["status"], "unknown")
        self.assertEqual(scored["match_breakdown"][0]["possible_contribution"], 0.0)

    def test_phase6_required_preference_excludes_proven_mismatch(self):
        profile = map_text_to_filters("Montessori")
        matching = {**SCHOOL, "pedagogy": "Montessori"}
        mismatch = {**SCHOOL, "school_id": "B", "pedagogy": "Play-based"}
        unknown = {**SCHOOL, "school_id": "C", "pedagogy": None}
        ranked = rank_schools(profile, [mismatch, unknown, matching])
        self.assertEqual({item["school_id"] for item in ranked}, {SCHOOL["school_id"], "C"})

    def test_phase6_importance_changes_ranking_contributions(self):
        profile = map_text_to_filters("SPARK with transport")
        for item in profile["preference_items"]:
            item["importance"] = "nice_to_have" if item["attribute"] == "spark_certified" else "high_priority"
        spark_only = {**SCHOOL, "school_id": "A", "spark_certified": "Yes", "provision_of_transport": "No"}
        transport_only = {**SCHOOL, "school_id": "B", "spark_certified": "No", "provision_of_transport": "Yes"}
        ranked = rank_schools(profile, [spark_only, transport_only])
        self.assertEqual(ranked[0]["school_id"], "B")
        self.assertGreater(ranked[0]["match_score"], ranked[1]["match_score"])

    def test_phase6_tied_scores_use_evidence_confidence(self):
        profile = map_text_to_filters("SPARK with transport")
        complete = {**SCHOOL, "school_id": "A", "spark_certified": "Yes", "provision_of_transport": "Yes"}
        partial = {**SCHOOL, "school_id": "B", "spark_certified": "Yes", "provision_of_transport": None}
        ranked = rank_schools(profile, [partial, complete])
        self.assertEqual(ranked[0]["school_id"], "A")
        self.assertGreater(ranked[0]["profile_confidence"], ranked[1]["profile_confidence"])

    def test_postal_coordinate_maps_to_sengkang_planning_area(self):
        boundary_file = (
            Path(__file__).resolve().parents[3]
            / "data"
            / "raw"
            / "MasterPlan2025PlanningArea.geojson"
        )
        town = proximity.planning_area_for_point(
            {"latitude": 1.393458, "longitude": 103.900515}, boundary_file
        )
        self.assertEqual(town, "SENGKANG")

    @patch("stage1.proximity._authenticate_onemap")
    @patch("stage1.proximity.time.time", return_value=1000)
    def test_onemap_token_is_cached_and_refreshed_before_expiry(self, now, authenticate):
        authenticate.side_effect = [("first", 2000), ("second", 3000)]
        proximity._cached_token = None
        proximity._token_expiry = 0
        self.assertEqual(proximity.get_onemap_token(), "first")
        self.assertEqual(proximity.get_onemap_token(), "first")
        now.return_value = 1800
        self.assertEqual(proximity.get_onemap_token(), "second")
        self.assertEqual(authenticate.call_count, 2)

    def test_proximity_filter_crosses_town_boundaries(self):
        centres = [{"centre_code": "NEAR"}, {"centre_code": "FAR"}]
        locations = {
            "NEAR": {"latitude": 1.3005, "longitude": 103.8},
            "FAR": {"latitude": 1.32, "longitude": 103.8},
        }
        result = filter_within_radius(
            centres,
            {"latitude": 1.3, "longitude": 103.8},
            locations,
            radius_km=1.0,
        )
        self.assertEqual([item["centre_code"] for item in result], ["NEAR"])
        self.assertLess(result[0]["distance_km"], 1.0)

    def test_stage1_location_uses_numeric_postal_code(self):
        query, params = build_stage1_query({"town": "540231"})
        self.assertIn("p.postal_code = $postal_code", query)
        self.assertEqual(params["postal_code"], 540231)

    def test_stage1_location_uses_case_insensitive_town_name(self):
        query, params = build_stage1_query({"town": "Sengkang"})
        self.assertIn("toLower(toString(t.name)) = toLower($town)", query)
        self.assertEqual(params["town"], "Sengkang")

    def test_stage1_filters_after_optional_matches(self):
        query, params = build_stage1_query({"philosophy": "Montessori"})
        self.assertLess(query.index("WITH p, t, c"), query.index("WHERE"))
        self.assertEqual(params["philosophy"], "Montessori")

    @patch("pipeline.run_from_text", return_value=[SCHOOL])
    def test_stage1_output_flows_into_stage2(self, stage1_search):
        result = search_and_evaluate(
            "play-based learning",
            dob=dt.date(2023, 6, 10),
            admission_date=dt.date(2026, 6, 10),
            ghi=4500,
            basic_subsidy=600,
        )
        stage1_search.assert_called_once_with(text="play-based learning", town=None)
        self.assertEqual(result[0]["centre_code"], "ST0001")
        self.assertEqual(result[0]["net_monthly_fee"], 160.0)

    def test_stage2_reads_stage1_json_and_writes_result(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "stage1.json"
            output_path = Path(directory) / "stage2.json"
            input_path.write_text(json.dumps([SCHOOL]), encoding="utf-8")

            result = run_from_file(
                input_path,
                dob=dt.date(2023, 6, 10),
                admission_date=dt.date(2026, 6, 10),
                ghi=4500,
                basic_subsidy=600,
                output_path=output_path,
            )

            saved = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(result, saved)
            self.assertEqual(saved[0]["net_monthly_fee"], 160.0)


if __name__ == "__main__":
    unittest.main()
