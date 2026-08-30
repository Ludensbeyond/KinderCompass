"""Explicitly registered tools for selected-school evidence orchestration."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, StructuredTool

from ..pipeline.stage1.web_rag import retrieve
from .contracts import (
    EvidenceCitation,
    RetrievedEvidence,
    SelectedSchoolAgentRequest,
)


SELECTED_SCHOOL_EVIDENCE_TOOL_NAME = "search_selected_school_evidence"


def create_selected_school_evidence_tool(index: dict[str, Any]) -> BaseTool:
    """Register school-isolated retrieval against a server-supplied evidence index."""

    def search_selected_school_evidence(
        question: str,
        school_id: str,
        school_name: str,
    ) -> list[RetrievedEvidence]:
        request = SelectedSchoolAgentRequest(
            question=question,
            school_id=school_id,
            school_name=school_name,
        )
        matches = retrieve(index, request.school_id, request.question)
        return [
            RetrievedEvidence(
                school_id=match["school_id"],
                chunk_id=match["chunk_id"],
                text=match["text"],
                citation=EvidenceCitation(
                    citation_id=match["citation"]["chunk_id"],
                    school_id=match["school_id"],
                    chunk_id=match["citation"]["chunk_id"],
                    url=match["citation"]["url"],
                    title=match["citation"]["title"],
                    retrieved_at=match["citation"]["retrieved_at"],
                ),
            )
            for match in matches
            if match.get("school_id") == request.school_id
        ]

    return StructuredTool.from_function(
        func=search_selected_school_evidence,
        name=SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
        description=(
            "Search retrieved webpage evidence for exactly one authoritative selected "
            "school. Use this before answering a question about that school's webpage."
        ),
        args_schema=SelectedSchoolAgentRequest,
        infer_schema=False,
    )
