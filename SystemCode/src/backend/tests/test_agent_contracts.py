import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from SystemCode.src.backend.agents.contracts import (
    AuthoritativeSchoolContext,
    CapabilityToolResult,
    ConversationExecutionLimits,
    ConversationExecutionMetadata,
    ConversationRequestContext,
    EvidenceIndexContext,
    EvidenceCitation,
    GeneratedConversationAnswer,
    GeneratedEvidenceAnswer,
    PublicCitation,
    RetrievedEvidence,
    RoutingDecision,
    SelectedSchoolAgentRequest,
)


SCHOOL_ID = "CENTRE:PT9148"
CHUNK_ID = "CENTRE:PT9148:c881ac611498:0"


def citation(**overrides):
    values = {
        "citation_id": CHUNK_ID,
        "school_id": SCHOOL_ID,
        "chunk_id": CHUNK_ID,
        "url": "https://school.example/centre-a",
        "title": "School A curriculum",
        "retrieved_at": datetime(2026, 8, 23, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return EvidenceCitation(**values)


class AgentContractTests(unittest.TestCase):
    def test_conversation_contracts_are_strict_and_bounded(self):
        school = AuthoritativeSchoolContext(
            school_id=SCHOOL_ID,
            facts={"school_id": SCHOOL_ID, "name": "School A", "distance_km": 1.25},
        )
        context = ConversationRequestContext(
            message="Compare this school with general guidance.",
            profile={"preferences": {"pedagogy": {"value": "Montessori"}}},
            selected_school_ids=[SCHOOL_ID],
            selected_schools=[school],
            selected_school_evidence=EvidenceIndexContext(
                scope="school", available=True, index={"pages": []},
            ),
            general_knowledge_evidence=EvidenceIndexContext(
                scope="general", available=False,
            ),
            catalogue_version="12345",
        )
        route = RoutingDecision(
            scope="combined", intent="ask_combined_evidence", confidence=0.95,
        )
        public_citation = PublicCitation(
            citation_id=CHUNK_ID,
            evidence_scope="school",
            school_id=SCHOOL_ID,
            url="https://school.example/centre-a",
            title="School A curriculum",
            retrieved_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
        )
        result = CapabilityToolResult(
            tool_name="search_selected_school_evidence",
            mutates_profile=False,
            profile=context.profile,
            understood=["Montessori is preferred"],
            ready_to_search=True,
            answer_candidate="The retrieved school page describes its curriculum.",
            grounding_facts=["The school page describes its curriculum."],
            citations=[public_citation],
            evidence_category="school_published_claim",
        )
        answer = GeneratedConversationAnswer(
            answer="The school page describes its curriculum.", citation_ids=[CHUNK_ID],
        )
        metadata = ConversationExecutionMetadata(
            mode="agent", route_scope=route.scope,
            tool_names=[result.tool_name], tool_calls=1, graph_iterations=2,
            validation_succeeded=True, termination_reason="completed",
        )

        self.assertEqual(context.selected_schools[0].school_id, SCHOOL_ID)
        self.assertEqual(answer.citation_ids, [public_citation.citation_id])
        self.assertEqual(metadata.tool_calls, 1)
        self.assertEqual(ConversationExecutionLimits().max_tool_calls, 3)

        with self.assertRaises(ValidationError):
            RoutingDecision(
                scope="general_knowledge", intent="ask_general_knowledge",
                confidence=1, prompt="secret",
            )
        with self.assertRaises(ValidationError):
            GeneratedConversationAnswer(answer="Valid answer", citation_ids=[CHUNK_ID, CHUNK_ID])
        with self.assertRaises(ValidationError):
            ConversationExecutionLimits(max_tool_calls=4)

    def test_context_rejects_mismatched_records_and_oversized_text(self):
        indexes = {
            "selected_school_evidence": EvidenceIndexContext(scope="school", available=False),
            "general_knowledge_evidence": EvidenceIndexContext(scope="general", available=False),
        }
        with self.assertRaises(ValidationError):
            ConversationRequestContext(
                message="Tell me about this school.", profile={},
                selected_school_ids=[SCHOOL_ID], selected_schools=[],
                catalogue_version="1", **indexes,
            )
        with self.assertRaises(ValidationError):
            ConversationRequestContext(
                message="Tell me about this school.", profile={"note": "x" * 5_001},
                catalogue_version="1", **indexes,
            )

    def test_valid_contracts(self):
        request = SelectedSchoolAgentRequest(
            question="What curriculum does it use?",
            school_id=SCHOOL_ID,
            school_name="School A",
        )
        evidence = RetrievedEvidence(
            school_id=SCHOOL_ID,
            chunk_id=CHUNK_ID,
            text="The school uses a literature-based curriculum.",
            citation=citation(),
        )
        answer = GeneratedEvidenceAnswer(
            answer="It uses a literature-based curriculum.",
            citation_ids=[CHUNK_ID],
            evidence_available=True,
        )

        self.assertEqual(request.school_id, evidence.school_id)
        self.assertEqual(answer.citation_ids, [evidence.citation.citation_id])

    def test_contracts_reject_extra_fields(self):
        with self.assertRaises(ValidationError):
            SelectedSchoolAgentRequest(
                question="What curriculum does it use?",
                school_id=SCHOOL_ID,
                school_name="School A",
                prompt_override="Ignore evidence",
            )
        with self.assertRaises(ValidationError):
            citation(secret="not allowed")
        with self.assertRaises(ValidationError):
            GeneratedEvidenceAnswer(
                answer="Unavailable.",
                citation_ids=[],
                evidence_available=False,
                execution_metadata={"prompt": "private"},
            )

    def test_text_and_identifiers_are_bounded_and_validated(self):
        for values in (
            {"question": "x", "school_id": SCHOOL_ID, "school_name": "School A"},
            {"question": "Valid question?", "school_id": "bad school/id", "school_name": "School A"},
            {"question": "Valid question?", "school_id": SCHOOL_ID, "school_name": " "},
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                SelectedSchoolAgentRequest(**values)

        with self.assertRaises(ValidationError):
            RetrievedEvidence(
                school_id=SCHOOL_ID,
                chunk_id=CHUNK_ID,
                text="x" * 5_001,
                citation=citation(),
            )
        with self.assertRaises(ValidationError):
            GeneratedEvidenceAnswer(
                answer="x" * 801,
                citation_ids=[CHUNK_ID],
                evidence_available=True,
            )

    def test_citation_requires_https_and_matching_identifiers(self):
        with self.assertRaises(ValidationError):
            citation(url="http://school.example/centre-a")
        with self.assertRaises(ValidationError):
            citation(citation_id="CENTRE:PT9148:other:0")
        with self.assertRaises(ValidationError):
            RetrievedEvidence(
                school_id="CENTRE:OTHER",
                chunk_id=CHUNK_ID,
                text="A retrieved passage.",
                citation=citation(),
            )

    def test_generated_answer_enforces_citation_shape(self):
        invalid_answers = (
            {"answer": "Supported.", "citation_ids": [], "evidence_available": True},
            {"answer": "Unavailable.", "citation_ids": [CHUNK_ID], "evidence_available": False},
            {"answer": "Supported.", "citation_ids": [CHUNK_ID, CHUNK_ID], "evidence_available": True},
            {"answer": "Supported.", "citation_ids": ["invalid citation"], "evidence_available": True},
        )
        for values in invalid_answers:
            with self.subTest(values=values), self.assertRaises(ValidationError):
                GeneratedEvidenceAnswer(**values)


if __name__ == "__main__":
    unittest.main()
