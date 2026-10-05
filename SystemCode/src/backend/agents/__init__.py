"""Bounded agent orchestration for backend-only capabilities."""

from .config import WebRagAnswerMode, get_web_rag_answer_mode
from .contracts import (
    DecisionToolRequest,
    EvidenceCitation,
    EvidenceSearchToolRequest,
    GeneralKnowledgeEvidence,
    GeneratedEvidenceAnswer,
    ConversationSupervisorResult,
    PreferenceStateToolRequest,
    RetrievedEvidence,
    SelectedSchoolAgentRequest,
    StructuredSchoolFactsToolRequest,
)
from .model_factory import (
    ModelFactoryError,
    ModelFactoryErrorCode,
    create_agent_model,
)

__all__ = [
    "EvidenceCitation",
    "EvidenceSearchToolRequest",
    "GeneralKnowledgeEvidence",
    "DecisionToolRequest",
    "GeneratedEvidenceAnswer",
    "ConversationSupervisorResult",
    "ModelFactoryError",
    "ModelFactoryErrorCode",
    "RetrievedEvidence",
    "SelectedSchoolAgentRequest",
    "SelectedSchoolGraphLimits",
    "SelectedSchoolGraphResult",
    "SELECTED_SCHOOL_EVIDENCE_TOOL_NAME",
    "GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME",
    "EVIDENCE_TOOL_NAMES",
    "CuratedGeneralKnowledgeRetriever",
    "GeneralKnowledgeRetriever",
    "CONTINUE_PENDING_PREFERENCE_FLOW_TOOL_NAME",
    "PREFERENCE_STATE_TOOL_NAMES",
    "PreferenceStateToolRequest",
    "StructuredSchoolFactsToolRequest",
    "RESET_PREFERENCES_TOOL_NAME",
    "UPDATE_PREFERENCES_TOOL_NAME",
    "DECISION_AND_CALCULATION_TOOL_NAMES",
    "ASSESS_SELECTED_SCHOOL_TOOL_NAME",
    "COMPARE_SELECTED_SCHOOLS_TOOL_NAME",
    "EXPLAIN_EVIDENCE_PROVENANCE_TOOL_NAME",
    "EXPLAIN_SCHOOL_EXCLUSION_TOOL_NAME",
    "EXPLAIN_SELECTED_TRADEOFFS_TOOL_NAME",
    "EXPLAIN_TOP_RANKED_SCHOOL_TOOL_NAME",
    "FIND_CLOSEST_SCHOOL_TOOL_NAME",
    "QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME",
    "RECOMMEND_SELECTED_SCHOOL_TOOL_NAME",
    "RUN_WHAT_IF_SCENARIO_TOOL_NAME",
    "WebRagAnswerMode",
    "create_agent_model",
    "create_selected_school_evidence_graph",
    "create_selected_school_evidence_tool",
    "create_evidence_tools",
    "create_preference_state_tools",
    "create_decision_and_calculation_tools",
    "create_structured_school_facts_tool",
    "get_web_rag_answer_mode",
    "run_selected_school_evidence_graph",
    "ConversationSupervisorState",
    "create_conversation_supervisor_graph",
    "ConversationSupervisorRunResult",
    "run_conversation_supervisor",
    "validate_conversation_supervisor_state",
    "ConversationEvaluationCase",
    "ConversationEvaluationRun",
    "ConversationEvaluationSet",
    "evaluate_conversation_cases",
    "ConversationObservation",
    "build_conversation_observation",
    "emit_conversation_observation",
]


def __getattr__(name: str):
    """Keep optional LangChain tool dependencies lazy at package import time."""

    if name in {
        "ConversationEvaluationCase", "ConversationEvaluationRun",
        "ConversationEvaluationSet", "evaluate_conversation_cases",
    }:
        from .evaluation import (
            ConversationEvaluationCase,
            ConversationEvaluationRun,
            ConversationEvaluationSet,
            evaluate_conversation_cases,
        )

        exports = {
            "ConversationEvaluationCase": ConversationEvaluationCase,
            "ConversationEvaluationRun": ConversationEvaluationRun,
            "ConversationEvaluationSet": ConversationEvaluationSet,
            "evaluate_conversation_cases": evaluate_conversation_cases,
        }
        return exports[name]

    if name in {
        "ConversationObservation", "build_conversation_observation",
        "emit_conversation_observation",
    }:
        from .observability import (
            ConversationObservation,
            build_conversation_observation,
            emit_conversation_observation,
        )

        exports = {
            "ConversationObservation": ConversationObservation,
            "build_conversation_observation": build_conversation_observation,
            "emit_conversation_observation": emit_conversation_observation,
        }
        return exports[name]

    if name in {
        "SelectedSchoolGraphLimits",
        "SelectedSchoolGraphResult",
        "create_selected_school_evidence_graph",
        "run_selected_school_evidence_graph",
        "ConversationSupervisorState",
        "create_conversation_supervisor_graph",
        "ConversationSupervisorRunResult",
        "run_conversation_supervisor",
        "validate_conversation_supervisor_state",
    }:
        from .graph import (
            SelectedSchoolGraphLimits,
            SelectedSchoolGraphResult,
            create_selected_school_evidence_graph,
            run_selected_school_evidence_graph,
        )
        from .supervisor import (
            ConversationSupervisorState,
            create_conversation_supervisor_graph,
        )
        from .validation import (
            ConversationSupervisorRunResult,
            run_conversation_supervisor,
            validate_conversation_supervisor_state,
        )

        exports = {
            "SelectedSchoolGraphLimits": SelectedSchoolGraphLimits,
            "SelectedSchoolGraphResult": SelectedSchoolGraphResult,
            "create_selected_school_evidence_graph": create_selected_school_evidence_graph,
            "run_selected_school_evidence_graph": run_selected_school_evidence_graph,
            "ConversationSupervisorState": ConversationSupervisorState,
            "create_conversation_supervisor_graph": create_conversation_supervisor_graph,
            "ConversationSupervisorRunResult": ConversationSupervisorRunResult,
            "run_conversation_supervisor": run_conversation_supervisor,
            "validate_conversation_supervisor_state": validate_conversation_supervisor_state,
        }
        return exports[name]

    if name in {
        "CONTINUE_PENDING_PREFERENCE_FLOW_TOOL_NAME",
        "PREFERENCE_STATE_TOOL_NAMES",
        "RESET_PREFERENCES_TOOL_NAME",
        "SELECTED_SCHOOL_EVIDENCE_TOOL_NAME",
        "GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME",
        "EVIDENCE_TOOL_NAMES",
        "CuratedGeneralKnowledgeRetriever",
        "GeneralKnowledgeRetriever",
        "UPDATE_PREFERENCES_TOOL_NAME",
        "create_preference_state_tools",
        "create_selected_school_evidence_tool",
        "create_evidence_tools",
        "DECISION_AND_CALCULATION_TOOL_NAMES",
        "ASSESS_SELECTED_SCHOOL_TOOL_NAME",
        "COMPARE_SELECTED_SCHOOLS_TOOL_NAME",
        "EXPLAIN_EVIDENCE_PROVENANCE_TOOL_NAME",
        "EXPLAIN_SCHOOL_EXCLUSION_TOOL_NAME",
        "EXPLAIN_SELECTED_TRADEOFFS_TOOL_NAME",
        "EXPLAIN_TOP_RANKED_SCHOOL_TOOL_NAME",
        "FIND_CLOSEST_SCHOOL_TOOL_NAME",
        "QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME",
        "RECOMMEND_SELECTED_SCHOOL_TOOL_NAME",
        "RUN_WHAT_IF_SCENARIO_TOOL_NAME",
        "create_decision_and_calculation_tools",
        "create_structured_school_facts_tool",
    }:
        from .tools import (
            CONTINUE_PENDING_PREFERENCE_FLOW_TOOL_NAME,
            PREFERENCE_STATE_TOOL_NAMES,
            RESET_PREFERENCES_TOOL_NAME,
            SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
            GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME,
            EVIDENCE_TOOL_NAMES,
            CuratedGeneralKnowledgeRetriever,
            GeneralKnowledgeRetriever,
            UPDATE_PREFERENCES_TOOL_NAME,
            DECISION_AND_CALCULATION_TOOL_NAMES,
            ASSESS_SELECTED_SCHOOL_TOOL_NAME,
            COMPARE_SELECTED_SCHOOLS_TOOL_NAME,
            EXPLAIN_EVIDENCE_PROVENANCE_TOOL_NAME,
            EXPLAIN_SCHOOL_EXCLUSION_TOOL_NAME,
            EXPLAIN_SELECTED_TRADEOFFS_TOOL_NAME,
            EXPLAIN_TOP_RANKED_SCHOOL_TOOL_NAME,
            FIND_CLOSEST_SCHOOL_TOOL_NAME,
            QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME,
            RECOMMEND_SELECTED_SCHOOL_TOOL_NAME,
            RUN_WHAT_IF_SCENARIO_TOOL_NAME,
            create_decision_and_calculation_tools,
            create_preference_state_tools,
            create_selected_school_evidence_tool,
            create_evidence_tools,
            create_structured_school_facts_tool,
        )

        exports = {
            "CONTINUE_PENDING_PREFERENCE_FLOW_TOOL_NAME": CONTINUE_PENDING_PREFERENCE_FLOW_TOOL_NAME,
            "PREFERENCE_STATE_TOOL_NAMES": PREFERENCE_STATE_TOOL_NAMES,
            "RESET_PREFERENCES_TOOL_NAME": RESET_PREFERENCES_TOOL_NAME,
            "SELECTED_SCHOOL_EVIDENCE_TOOL_NAME": SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
            "GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME": GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME,
            "EVIDENCE_TOOL_NAMES": EVIDENCE_TOOL_NAMES,
            "CuratedGeneralKnowledgeRetriever": CuratedGeneralKnowledgeRetriever,
            "GeneralKnowledgeRetriever": GeneralKnowledgeRetriever,
            "UPDATE_PREFERENCES_TOOL_NAME": UPDATE_PREFERENCES_TOOL_NAME,
            "DECISION_AND_CALCULATION_TOOL_NAMES": DECISION_AND_CALCULATION_TOOL_NAMES,
            "ASSESS_SELECTED_SCHOOL_TOOL_NAME": ASSESS_SELECTED_SCHOOL_TOOL_NAME,
            "COMPARE_SELECTED_SCHOOLS_TOOL_NAME": COMPARE_SELECTED_SCHOOLS_TOOL_NAME,
            "EXPLAIN_EVIDENCE_PROVENANCE_TOOL_NAME": EXPLAIN_EVIDENCE_PROVENANCE_TOOL_NAME,
            "EXPLAIN_SCHOOL_EXCLUSION_TOOL_NAME": EXPLAIN_SCHOOL_EXCLUSION_TOOL_NAME,
            "EXPLAIN_SELECTED_TRADEOFFS_TOOL_NAME": EXPLAIN_SELECTED_TRADEOFFS_TOOL_NAME,
            "EXPLAIN_TOP_RANKED_SCHOOL_TOOL_NAME": EXPLAIN_TOP_RANKED_SCHOOL_TOOL_NAME,
            "FIND_CLOSEST_SCHOOL_TOOL_NAME": FIND_CLOSEST_SCHOOL_TOOL_NAME,
            "QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME": QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME,
            "RECOMMEND_SELECTED_SCHOOL_TOOL_NAME": RECOMMEND_SELECTED_SCHOOL_TOOL_NAME,
            "RUN_WHAT_IF_SCENARIO_TOOL_NAME": RUN_WHAT_IF_SCENARIO_TOOL_NAME,
            "create_decision_and_calculation_tools": create_decision_and_calculation_tools,
            "create_preference_state_tools": create_preference_state_tools,
            "create_selected_school_evidence_tool": create_selected_school_evidence_tool,
            "create_evidence_tools": create_evidence_tools,
            "create_structured_school_facts_tool": create_structured_school_facts_tool,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
