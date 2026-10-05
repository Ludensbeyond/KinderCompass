import unittest

from langchain_core.tools import BaseTool

from SystemCode.src.backend.agents import (
    SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
    RetrievedEvidence,
    SelectedSchoolAgentRequest,
    create_selected_school_evidence_tool,
)


SCHOOL_A = "CENTRE:PT9148"
SCHOOL_B = "CENTRE:PT9999"


def chunk(school_id, suffix, text):
    chunk_id = f"{school_id}:c881ac611498:{suffix}"
    return {
        "chunk_id": chunk_id,
        "school_id": school_id,
        "text": text,
        "source_url": f"https://school.example/{school_id.lower()}",
        "title": f"{school_id} curriculum",
        "retrieved_at": "2026-08-23T12:00:00+00:00",
    }


def page(school_id, chunks):
    return {"school_id": school_id, "chunks": chunks}


def invoke(tool, school_id=SCHOOL_A, question="What curriculum does it use?"):
    return tool.invoke(
        {
            "question": question,
            "school_id": school_id,
            "school_name": "School A",
        }
    )


class SelectedSchoolEvidenceToolTests(unittest.TestCase):
    def test_registered_tool_returns_typed_evidence(self):
        index = {
            "pages": [
                page(
                    SCHOOL_A,
                    [chunk(SCHOOL_A, 0, "Our literature-based curriculum supports learning.")],
                )
            ]
        }

        tool = create_selected_school_evidence_tool(index)
        result = invoke(tool)

        self.assertIsInstance(tool, BaseTool)
        self.assertEqual(tool.name, SELECTED_SCHOOL_EVIDENCE_TOOL_NAME)
        self.assertIs(tool.args_schema, SelectedSchoolAgentRequest)
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], RetrievedEvidence)
        self.assertEqual(result[0].school_id, SCHOOL_A)
        self.assertEqual(result[0].citation.citation_id, result[0].chunk_id)

    def test_missing_school_returns_no_evidence(self):
        index = {
            "pages": [
                page(
                    SCHOOL_B,
                    [chunk(SCHOOL_B, 0, "Our literature-based curriculum supports learning.")],
                )
            ]
        }

        self.assertEqual(invoke(create_selected_school_evidence_tool(index)), [])

    def test_school_with_empty_evidence_returns_no_evidence(self):
        index = {"pages": [page(SCHOOL_A, [])]}

        self.assertEqual(invoke(create_selected_school_evidence_tool(index)), [])

    def test_cross_school_chunks_are_excluded(self):
        index = {
            "pages": [
                page(
                    SCHOOL_A,
                    [
                        chunk(SCHOOL_B, 0, "A literature-based curriculum from another school."),
                        chunk(SCHOOL_A, 1, "Our play-based curriculum supports exploration."),
                    ],
                ),
                page(
                    SCHOOL_B,
                    [chunk(SCHOOL_B, 1, "A literature-based curriculum from another school.")],
                ),
            ]
        }

        result = invoke(create_selected_school_evidence_tool(index))

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].chunk_id, f"{SCHOOL_A}:c881ac611498:1")
        self.assertEqual(result[0].text, "Our play-based curriculum supports exploration.")
        self.assertEqual({item.school_id for item in result}, {SCHOOL_A})
        self.assertEqual({item.citation.school_id for item in result}, {SCHOOL_A})


if __name__ == "__main__":
    unittest.main()
