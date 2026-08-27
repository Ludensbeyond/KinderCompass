"""Bounded agent orchestration for backend-only capabilities."""

from .config import WebRagAnswerMode, get_web_rag_answer_mode
from .contracts import (
    EvidenceCitation,
    GeneratedEvidenceAnswer,
    RetrievedEvidence,
    SelectedSchoolAgentRequest,
)
from .model_factory import (
    ModelFactoryError,
    ModelFactoryErrorCode,
    create_agent_model,
)

__all__ = [
    "EvidenceCitation",
    "GeneratedEvidenceAnswer",
    "ModelFactoryError",
    "ModelFactoryErrorCode",
    "RetrievedEvidence",
    "SelectedSchoolAgentRequest",
    "SELECTED_SCHOOL_EVIDENCE_TOOL_NAME",
    "WebRagAnswerMode",
    "create_agent_model",
    "create_selected_school_evidence_tool",
    "get_web_rag_answer_mode",
]


def __getattr__(name: str):
    """Keep optional LangChain tool dependencies lazy at package import time."""

    if name in {"SELECTED_SCHOOL_EVIDENCE_TOOL_NAME", "create_selected_school_evidence_tool"}:
        from .tools import (
            SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
            create_selected_school_evidence_tool,
        )

        exports = {
            "SELECTED_SCHOOL_EVIDENCE_TOOL_NAME": SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
            "create_selected_school_evidence_tool": create_selected_school_evidence_tool,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
