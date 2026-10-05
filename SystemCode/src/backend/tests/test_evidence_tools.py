import unittest
from copy import deepcopy

from langchain_core.tools import BaseTool
from pydantic import ValidationError

from SystemCode.src.backend.agents import (
    EVIDENCE_TOOL_NAMES,
    GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME,
    SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
    EvidenceSearchToolRequest,
    create_evidence_tools,
)
from SystemCode.src.backend.agents.contracts import (
    AuthoritativeSchoolContext,
    CapabilityToolResult,
    ConversationRequestContext,
    EvidenceIndexContext,
)


SCHOOL_A = "CENTRE:A"
SCHOOL_B = "CENTRE:B"


def school_chunk(school_id: str, suffix: str, text: str) -> dict:
    return {
        "chunk_id": f"{school_id}:page:{suffix}",
        "school_id": school_id,
        "text": text,
        "source_url": f"https://school.example/{school_id.lower()}",
        "title": "Official programme page",
        "retrieved_at": "2026-08-14T00:00:00+00:00",
    }


SCHOOL_INDEX = {
    "pages": [
        {
            "school_id": SCHOOL_A,
            "chunks": [
                school_chunk(SCHOOL_A, "0", "Our play-based curriculum supports exploration."),
                school_chunk(SCHOOL_B, "forged", "Another branch uses Montessori."),
            ],
        },
        {
            "school_id": SCHOOL_B,
            "chunks": [school_chunk(SCHOOL_B, "0", "This branch uses Montessori.")],
        },
    ],
}

GENERAL_INDEX = {
    "chunks": [{
        "chunk_id": "GENERAL:play:0",
        "topic": "play-based learning",
        "text": "Play-based learning uses active, hands-on experiences to support development.",
        "source_url": "https://authority.example/play",
        "title": "Play guidance",
        "authority": "Education Authority",
        "retrieved_at": "2026-08-14",
    }],
}


def context(*, selected=True, school_index=SCHOOL_INDEX, general_index=GENERAL_INDEX):
    schools = []
    if selected:
        schools = [AuthoritativeSchoolContext(
            school_id=SCHOOL_A,
            facts={"school_id": SCHOOL_A, "name": "Alpha Preschool"},
        )]
    return ConversationRequestContext(
        message="This school uses play-based learning. What does that mean?",
        profile={"preferences": {"pedagogy": {"value": "Play-based"}}},
        selected_school_ids=[item.school_id for item in schools],
        selected_schools=schools,
        selected_school_evidence=EvidenceIndexContext(
            scope="school", available=school_index is not None, index=school_index,
        ),
        general_knowledge_evidence=EvidenceIndexContext(
            scope="general", available=general_index is not None, index=general_index,
        ),
        catalogue_version="test-catalogue",
    )


def by_name(tools):
    return {tool.name: tool for tool in tools}


class ConversationEvidenceToolTests(unittest.TestCase):
    def test_registers_two_strict_read_only_tools(self):
        tools = create_evidence_tools(context())

        self.assertEqual({tool.name for tool in tools}, EVIDENCE_TOOL_NAMES)
        self.assertTrue(all(isinstance(tool, BaseTool) for tool in tools))
        self.assertTrue(all(tool.args_schema is EvidenceSearchToolRequest for tool in tools))
        with self.assertRaises(ValidationError):
            tools[0].invoke({
                "question": "What curriculum does it use?",
                "school_id": SCHOOL_B,
            })

    def test_selected_school_search_is_context_scoped_and_grounded(self):
        turn = context()
        snapshot = deepcopy(turn)
        result = by_name(create_evidence_tools(turn))[
            SELECTED_SCHOOL_EVIDENCE_TOOL_NAME
        ].invoke({"question": "What curriculum does it use?"})

        self.assertIsInstance(result, CapabilityToolResult)
        self.assertFalse(result.mutates_profile)
        self.assertEqual(result.evidence_category, "school_published_claim")
        self.assertEqual(len(result.citations), 1)
        self.assertEqual(result.citations[0].school_id, SCHOOL_A)
        self.assertEqual(result.citations[0].evidence_scope, "school")
        self.assertNotIn("Montessori", " ".join(result.grounding_facts))
        self.assertEqual(turn, snapshot)

    def test_general_search_uses_typed_curated_adapter(self):
        result = by_name(create_evidence_tools(context()))[
            GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME
        ].invoke({"question": "Explain play-based learning"})

        self.assertIn("hands-on experiences", result.answer_candidate)
        self.assertEqual(result.evidence_category, "authoritative_fact")
        self.assertEqual(len(result.citations), 1)
        self.assertEqual(result.citations[0].evidence_scope, "general")
        self.assertEqual(result.citations[0].authority, "Education Authority")
        self.assertIsNone(result.citations[0].school_id)

    def test_combined_answer_can_call_both_without_mixing_citation_scopes(self):
        tools = by_name(create_evidence_tools(context()))
        school = tools[SELECTED_SCHOOL_EVIDENCE_TOOL_NAME].invoke({
            "question": "Does this school use play-based learning?",
        })
        general = tools[GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME].invoke({
            "question": "What does play-based learning mean?",
        })

        self.assertEqual(
            {item.evidence_scope for item in school.citations + general.citations},
            {"school", "general"},
        )
        self.assertTrue(all(item.school_id == SCHOOL_A for item in school.citations))
        self.assertTrue(all(item.school_id is None for item in general.citations))

    def test_combined_conversational_wording_does_not_dilute_school_retrieval(self):
        tools = by_name(create_evidence_tools(context()))
        question = (
            "What does this selected school say about play-based learning, "
            "and what does that mean generally?"
        )

        school = tools[SELECTED_SCHOOL_EVIDENCE_TOOL_NAME].invoke({
            "question": question,
        })

        self.assertEqual(len(school.citations), 1)
        self.assertEqual(school.citations[0].school_id, SCHOOL_A)
        self.assertIn("play-based", " ".join(school.grounding_facts).lower())

    def test_missing_context_and_no_match_are_unavailable_not_negative(self):
        tools = by_name(create_evidence_tools(context(
            selected=False, school_index=None, general_index=None,
        )))
        school = tools[SELECTED_SCHOOL_EVIDENCE_TOOL_NAME].invoke({
            "question": "Does it offer transport?",
        })
        general = tools[GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME].invoke({
            "question": "What is an unsupported topic?",
        })

        self.assertIn("Select one preschool", school.answer_candidate)
        self.assertIn("unavailable", general.answer_candidate)
        self.assertEqual(school.citations, [])
        self.assertEqual(general.citations, [])
        self.assertEqual(school.evidence_category, "unknown")


if __name__ == "__main__":
    unittest.main()
