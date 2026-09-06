"""Explicitly registered tools for bounded conversation orchestration."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Protocol

from langchain_core.tools import BaseTool, StructuredTool

from ..pipeline.stage1.web_rag import retrieve, retrieve_general_evidence
from .contracts import (
    CapabilityToolResult,
    ConversationRequestContext,
    DecisionToolRequest,
    EvidenceCitation,
    EvidenceSearchToolRequest,
    GeneralKnowledgeEvidence,
    PreferenceStateToolRequest,
    PublicCitation,
    RetrievedEvidence,
    SelectedSchoolAgentRequest,
    StructuredSchoolFactsToolRequest,
)
from ..domain.models import FamilyDetails
from ..pipeline.stage1.conversation import update_conversation
from ..pipeline.stage1.intent_router import IntentResult
from ..services.conversation_calculations import (
    SchoolEvaluator,
    explain_school_exclusion,
    run_what_if_scenario,
)
from ..pipeline.stage1.nlp_mapper import summarize_profile


SELECTED_SCHOOL_EVIDENCE_TOOL_NAME = "search_selected_school_evidence"
GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME = "search_general_knowledge"
UPDATE_PREFERENCES_TOOL_NAME = "update_preferences"
RESET_PREFERENCES_TOOL_NAME = "reset_preferences"
CONTINUE_PENDING_PREFERENCE_FLOW_TOOL_NAME = "continue_pending_preference_flow"
FIND_CLOSEST_SCHOOL_TOOL_NAME = "find_closest_school"
EXPLAIN_TOP_RANKED_SCHOOL_TOOL_NAME = "explain_top_ranked_school"
COMPARE_SELECTED_SCHOOLS_TOOL_NAME = "compare_selected_schools"
EXPLAIN_SELECTED_TRADEOFFS_TOOL_NAME = "explain_selected_tradeoffs"
EXPLAIN_EVIDENCE_PROVENANCE_TOOL_NAME = "explain_evidence_provenance"
RECOMMEND_SELECTED_SCHOOL_TOOL_NAME = "recommend_selected_school"
ASSESS_SELECTED_SCHOOL_TOOL_NAME = "assess_selected_school"
RUN_WHAT_IF_SCENARIO_TOOL_NAME = "run_what_if_scenario"
EXPLAIN_SCHOOL_EXCLUSION_TOOL_NAME = "explain_school_exclusion"
QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME = "query_structured_school_facts"

PREFERENCE_STATE_TOOL_NAMES = frozenset({
    UPDATE_PREFERENCES_TOOL_NAME,
    RESET_PREFERENCES_TOOL_NAME,
    CONTINUE_PENDING_PREFERENCE_FLOW_TOOL_NAME,
})

DECISION_AND_CALCULATION_TOOL_NAMES = frozenset({
    FIND_CLOSEST_SCHOOL_TOOL_NAME,
    EXPLAIN_TOP_RANKED_SCHOOL_TOOL_NAME,
    COMPARE_SELECTED_SCHOOLS_TOOL_NAME,
    EXPLAIN_SELECTED_TRADEOFFS_TOOL_NAME,
    EXPLAIN_EVIDENCE_PROVENANCE_TOOL_NAME,
    RECOMMEND_SELECTED_SCHOOL_TOOL_NAME,
    ASSESS_SELECTED_SCHOOL_TOOL_NAME,
    RUN_WHAT_IF_SCENARIO_TOOL_NAME,
    EXPLAIN_SCHOOL_EXCLUSION_TOOL_NAME,
})

EVIDENCE_TOOL_NAMES = frozenset({
    SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
    GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME,
})


class StructuredSchoolFactsRepository(Protocol):
    """Allowlisted repository boundary used by the structured-facts tool."""

    def get_structured_facts(
        self, school_ids: list[str], operation: str,
    ) -> list[dict[str, Any]]: ...


class GeneralKnowledgeRetriever(Protocol):
    """Replaceable typed retrieval boundary for general guidance."""

    def search(
        self, question: str, *, limit: int = 3,
    ) -> list[GeneralKnowledgeEvidence]: ...


class CuratedGeneralKnowledgeRetriever:
    """Adapter for the current server-owned curated knowledge index."""

    def __init__(self, index: dict[str, Any]):
        self._index = index

    def search(
        self, question: str, *, limit: int = 3,
    ) -> list[GeneralKnowledgeEvidence]:
        matches = retrieve_general_evidence(
            self._index, question, limit=max(0, min(limit, 3)),
        )
        return [
            GeneralKnowledgeEvidence(
                chunk_id=str(match["chunk_id"]),
                text=str(match["text"]),
                citation=PublicCitation(
                    citation_id=str(match["citation"]["chunk_id"]),
                    evidence_scope="general",
                    url=str(match["citation"]["url"]),
                    title=str(match["citation"]["title"]),
                    retrieved_at=match["citation"]["retrieved_at"],
                    authority=match["citation"].get("authority"),
                ),
            )
            for match in matches
        ]


def _preference_result(tool_name: str, result: dict[str, Any]) -> CapabilityToolResult:
    """Translate the existing deterministic controller result into a tool result."""

    return CapabilityToolResult(
        tool_name=tool_name,
        mutates_profile=True,
        profile=result["profile"],
        understood=result.get("understood", []),
        ready_to_search=bool(result.get("ready_to_search")),
        answer_candidate=result["question"],
        grounding_facts=result.get("understood", []),
        citations=[],
        evidence_category=result.get("evidence_category", "unknown"),
    )


def _grounding_records(records: list[Any]) -> list[str]:
    """Serialize bounded authoritative inputs without exposing mutable objects."""

    grounded: list[str] = []
    for record in records[:30]:
        facts = record.facts if hasattr(record, "facts") else dict(record)
        projection = {
            key: facts.get(key)
            for key in (
                "school_id", "name", "match_score", "net_monthly_fee", "distance_km",
                "strengths", "tradeoffs", "match_breakdown", "status", "reason",
                "eligible", "policy_source",
            )
            if facts.get(key) is not None
        }
        grounded.append(json.dumps(projection, sort_keys=True, default=str)[:5_000])
    return grounded


def _read_only_result(
    tool_name: str, result: dict[str, Any], records: list[Any],
) -> CapabilityToolResult:
    answer = str(result["question"])
    if len(answer) > 800:
        answer = answer[:797].rstrip() + "..."
    return CapabilityToolResult(
        tool_name=tool_name,
        mutates_profile=False,
        profile=result["profile"],
        understood=result.get("understood", []),
        ready_to_search=bool(result.get("ready_to_search")),
        answer_candidate=answer,
        grounding_facts=_grounding_records(records),
        citations=[],
        evidence_category=result.get("evidence_category", "unknown"),
    )


def create_preference_state_tools(
    context: ConversationRequestContext,
    *,
    candidate_facets: dict[str, Any] | None = None,
) -> list[BaseTool]:
    """Register state-mutating tools bound to authoritative turn context.

    Every invocation starts from a fresh deep copy, so trying a tool cannot
    mutate the context or persist state. The existing deterministic controller
    remains the sole implementation of preference and pending-flow rules.
    """

    def run(tool_name: str, intent_name: str) -> CapabilityToolResult:
        deterministic = update_conversation(
            deepcopy(context.profile),
            context.message,
            classified_intent=IntentResult(intent=intent_name, confidence=1),
            candidate_facets=deepcopy(candidate_facets),
        )
        return _preference_result(tool_name, deterministic)

    def update_preferences(use_authoritative_context: bool = True) -> CapabilityToolResult:
        return run(UPDATE_PREFERENCES_TOOL_NAME, "update_preferences")

    def reset_preferences(use_authoritative_context: bool = True) -> CapabilityToolResult:
        return run(RESET_PREFERENCES_TOOL_NAME, "reset_preferences")

    def continue_pending_preference_flow(
        use_authoritative_context: bool = True,
    ) -> CapabilityToolResult:
        pending_fields = (
            "pending", "pending_contradiction", "pending_relaxation",
        )
        if not any(context.profile.get(field) for field in pending_fields):
            raise ValueError("no pending preference flow is available")
        return run(
            CONTINUE_PENDING_PREFERENCE_FLOW_TOOL_NAME,
            "update_preferences",
        )

    specifications = (
        (
            update_preferences,
            UPDATE_PREFERENCES_TOOL_NAME,
            "Apply the newest preference message using the authoritative current profile.",
        ),
        (
            reset_preferences,
            RESET_PREFERENCES_TOOL_NAME,
            "Reset preferences when the newest message explicitly requests a reset.",
        ),
        (
            continue_pending_preference_flow,
            CONTINUE_PENDING_PREFERENCE_FLOW_TOOL_NAME,
            "Continue the current importance, contradiction, or relaxation flow.",
        ),
    )
    return [
        StructuredTool.from_function(
            func=function,
            name=name,
            description=description,
            args_schema=PreferenceStateToolRequest,
            infer_schema=False,
        )
        for function, name, description in specifications
    ]


def create_decision_and_calculation_tools(
    context: ConversationRequestContext,
    evaluator: SchoolEvaluator,
) -> list[BaseTool]:
    """Register read-only decisions bound to repository-resolved turn context."""

    selected = [deepcopy(item.facts) for item in context.selected_schools]
    eligible = [deepcopy(item.facts) for item in context.eligible_schools]
    excluded = [deepcopy(item.facts) for item in context.excluded_schools]

    def conversation_result(tool_name: str, intent_name: str) -> CapabilityToolResult:
        deterministic = update_conversation(
            deepcopy(context.profile),
            context.message,
            deepcopy(selected),
            deepcopy(eligible),
            classified_intent=IntentResult(intent=intent_name, confidence=1),
        )
        records = eligible if intent_name in {
            "find_closest_preschool", "explain_top_ranked_preschool",
        } else selected
        return _read_only_result(tool_name, deterministic, records)

    def fixed(tool_name: str, intent_name: str):
        def invoke(use_authoritative_context: bool = True) -> CapabilityToolResult:
            return conversation_result(tool_name, intent_name)
        return invoke

    functions = [
        (FIND_CLOSEST_SCHOOL_TOOL_NAME, "find_closest_preschool", "Find the closest authoritative eligible school using server-calculated distances."),
        (EXPLAIN_TOP_RANKED_SCHOOL_TOOL_NAME, "explain_top_ranked_preschool", "Explain the first authoritative eligible result and its ranking evidence."),
        (COMPARE_SELECTED_SCHOOLS_TOOL_NAME, "compare_selected_preschools", "Compare the authoritative selected schools."),
        (EXPLAIN_SELECTED_TRADEOFFS_TOOL_NAME, "explain_selected_tradeoffs", "Explain recorded trade-offs for authoritative selected schools."),
        (EXPLAIN_EVIDENCE_PROVENANCE_TOOL_NAME, "explain_evidence_provenance", "Explain scorer-produced evidence provenance for authoritative selected schools."),
        (RECOMMEND_SELECTED_SCHOOL_TOOL_NAME, "recommend_selected_preschool", "Recommend among authoritative selected schools using deterministic ordering."),
        (ASSESS_SELECTED_SCHOOL_TOOL_NAME, "assess_selected_preschool", "Assess exactly one authoritative selected school."),
    ]
    tools = [
        StructuredTool.from_function(
            func=fixed(tool_name, intent_name),
            name=tool_name,
            description=description,
            args_schema=DecisionToolRequest,
            infer_schema=False,
        )
        for tool_name, intent_name, description in functions
    ]

    def what_if(use_authoritative_context: bool = True) -> CapabilityToolResult:
        records = selected if context.selected_school_ids else eligible
        school_ids = (
            context.selected_school_ids if context.selected_school_ids
            else context.eligible_school_ids
        )
        family = FamilyDetails.model_validate(context.family.model_dump()) if context.family else None
        result = run_what_if_scenario(
            context.message, list(school_ids), deepcopy(context.profile), family,
            evaluator, deepcopy(records),
        )
        return _read_only_result(RUN_WHAT_IF_SCENARIO_TOOL_NAME, result, records)

    def exclusion(use_authoritative_context: bool = True) -> CapabilityToolResult:
        family = FamilyDetails.model_validate(context.family.model_dump()) if context.family else None
        result = explain_school_exclusion(
            context.message, list(context.excluded_school_ids), deepcopy(context.profile),
            family, evaluator, deepcopy(excluded),
        )
        return _read_only_result(EXPLAIN_SCHOOL_EXCLUSION_TOOL_NAME, result, excluded)

    tools.extend([
        StructuredTool.from_function(
            func=what_if,
            name=RUN_WHAT_IF_SCENARIO_TOOL_NAME,
            description="Run a temporary fee or eligibility scenario using authoritative family and policy inputs.",
            args_schema=DecisionToolRequest,
            infer_schema=False,
        ),
        StructuredTool.from_function(
            func=exclusion,
            name=EXPLAIN_SCHOOL_EXCLUSION_TOOL_NAME,
            description="Explain Stage 2 exclusions from authoritative evaluated results.",
            args_schema=DecisionToolRequest,
            infer_schema=False,
        ),
    ])
    return tools


def _structured_fact_answer(records: list[dict[str, Any]], operation: str) -> str:
    if not records:
        return "Select at least one preschool so I can look up its structured catalogue facts."
    sections: list[str] = []
    for record in records:
        name = str(record.get("name") or "This preschool")
        facts = record.get("facts") or {}
        freshness = record.get("freshness", "unknown")
        updated = record.get("last_updated")
        freshness_note = ""
        if freshness == "stale":
            freshness_note = f" Data last updated {updated} may be stale."
        elif freshness == "unknown":
            freshness_note = " Data freshness is unknown."
        if not record.get("available"):
            sections.append(
                f"{name}: {operation.replace('_', ' ')} data is unavailable."
                f"{freshness_note}"
            )
            continue
        if operation == "food":
            detail = str(facts.get("food_offered"))
        elif operation == "vacancy":
            current = [
                f"{key.removesuffix('_vacancy_current_month').upper()}={value}"
                for key, value in facts.items()
                if key.endswith("_vacancy_current_month") and value not in (None, "")
            ]
            detail = "current-month " + ", ".join(current) if current else "vacancy data is present"
        elif operation == "fees":
            detail = (
                f"base fee ${float(facts['base_fee']):,.0f}"
                if facts.get("base_fee") is not None else "fee schedule is available"
            )
        elif operation == "programmes":
            levels = facts.get("care_levels") or []
            detail = "care levels " + ", ".join(map(str, levels)) if levels else "programme data is present"
        else:
            values = [f"{key.replace('_', ' ')}={value}" for key, value in facts.items() if value not in (None, "", [], {})]
            detail = ", ".join(values)
        sections.append(f"{name}: {detail}.{freshness_note}")
    answer = " ".join(sections)
    return answer if len(answer) <= 800 else answer[:797].rstrip() + "..."


def create_structured_school_facts_tool(
    context: ConversationRequestContext,
    repository: StructuredSchoolFactsRepository,
) -> BaseTool:
    """Create an allowlisted structured-fact tool over context-approved IDs."""

    allowed_ids = list(dict.fromkeys(
        context.selected_school_ids + context.eligible_school_ids + context.excluded_school_ids
    ))

    def query_structured_school_facts(
        operation: str,
        school_ids: list[str] | None = None,
    ) -> CapabilityToolResult:
        requested = school_ids or context.selected_school_ids
        if any(school_id not in allowed_ids for school_id in requested):
            raise ValueError("structured school facts require server-resolved school IDs")
        records = repository.get_structured_facts(list(requested), operation)
        grounding = [
            json.dumps(record, sort_keys=True, default=str)[:5_000]
            for record in records[:5]
        ]
        return CapabilityToolResult(
            tool_name=QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME,
            mutates_profile=False,
            profile=deepcopy(context.profile),
            understood=summarize_profile(context.profile),
            ready_to_search=bool(
                context.profile.get("hard_constraints") or context.profile.get("preferences")
            ),
            answer_candidate=_structured_fact_answer(records, operation),
            grounding_facts=grounding,
            citations=[],
            evidence_category="authoritative_fact" if any(
                record.get("available") for record in records
            ) else "unknown",
        )

    return StructuredTool.from_function(
        func=query_structured_school_facts,
        name=QUERY_STRUCTURED_SCHOOL_FACTS_TOOL_NAME,
        description=(
            "Query an allowlisted structured fact for server-resolved schools. "
            "Never accepts Cypher, arbitrary fields, or caller-supplied school records."
        ),
        args_schema=StructuredSchoolFactsToolRequest,
        infer_schema=False,
    )


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


def _bounded_answer(text: str) -> str:
    """Fit deterministic evidence wording into the shared answer contract."""

    compact = " ".join(text.split())
    return compact if len(compact) <= 800 else compact[:797].rstrip() + "..."


def _evidence_result(
    context: ConversationRequestContext,
    *,
    tool_name: str,
    answer: str,
    grounding_facts: list[str],
    citations: list[PublicCitation],
    evidence_category: str,
) -> CapabilityToolResult:
    return CapabilityToolResult(
        tool_name=tool_name,
        mutates_profile=False,
        profile=deepcopy(context.profile),
        understood=summarize_profile(context.profile),
        ready_to_search=bool(
            context.profile.get("hard_constraints") or context.profile.get("preferences")
        ),
        answer_candidate=_bounded_answer(answer),
        grounding_facts=grounding_facts[:3],
        citations=citations[:3],
        evidence_category=evidence_category,
    )


def create_evidence_tools(
    context: ConversationRequestContext,
    *,
    general_retriever: GeneralKnowledgeRetriever | None = None,
) -> list[BaseTool]:
    """Create school-scoped and general-scoped read-only evidence tools.

    The selected-school adapter reuses the original isolated retrieval tool,
    replacing caller-supplied scope with the single repository-resolved school
    in the turn context. General retrieval goes through a typed interface so a
    vector implementation can replace the curated-index adapter later without
    changing the capability result or supervisor contract.
    """

    school_index = context.selected_school_evidence.index
    selected_retrieval = (
        create_selected_school_evidence_tool(school_index)
        if school_index is not None else None
    )
    effective_general_retriever = general_retriever
    if effective_general_retriever is None and context.general_knowledge_evidence.index is not None:
        effective_general_retriever = CuratedGeneralKnowledgeRetriever(
            context.general_knowledge_evidence.index,
        )

    def search_selected(question: str) -> CapabilityToolResult:
        if not context.selected_schools:
            return _evidence_result(
                context,
                tool_name=SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
                answer="Select one preschool in the Results panel so I can search its official webpage.",
                grounding_facts=[], citations=[], evidence_category="unknown",
            )
        if len(context.selected_schools) != 1:
            return _evidence_result(
                context,
                tool_name=SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
                answer="Select only one preschool so webpage evidence cannot be mixed between schools.",
                grounding_facts=[], citations=[], evidence_category="unknown",
            )
        school = context.selected_schools[0]
        school_name = str(school.facts.get("name") or "this preschool")
        if selected_retrieval is None:
            return _evidence_result(
                context,
                tool_name=SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
                answer="Webpage evidence is unavailable for this preschool.",
                grounding_facts=[], citations=[], evidence_category="unknown",
            )
        passages = selected_retrieval.invoke({
            "question": question,
            "school_id": school.school_id,
            "school_name": school_name,
        })
        passages = [RetrievedEvidence.model_validate(item) for item in passages]
        if not passages:
            return _evidence_result(
                context,
                tool_name=SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
                answer=(
                    f"I could not find relevant webpage evidence for {school_name}. "
                    "That means the information is unavailable, not that the answer is no."
                ),
                grounding_facts=[], citations=[], evidence_category="unknown",
            )
        citations = [
            PublicCitation(
                citation_id=item.citation.citation_id,
                evidence_scope="school",
                school_id=school.school_id,
                url=item.citation.url,
                title=item.citation.title,
                retrieved_at=item.citation.retrieved_at,
            )
            for item in passages
        ]
        answer = (
            f"According to {school_name}'s official webpage, "
            + " ".join(item.text for item in passages[:2])
        )
        return _evidence_result(
            context,
            tool_name=SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
            answer=answer,
            grounding_facts=[item.text for item in passages],
            citations=citations,
            evidence_category="school_published_claim",
        )

    def search_general(question: str) -> CapabilityToolResult:
        if effective_general_retriever is None:
            return _evidence_result(
                context,
                tool_name=GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME,
                answer="General early-childhood guidance is unavailable.",
                grounding_facts=[], citations=[], evidence_category="unknown",
            )
        passages = [
            GeneralKnowledgeEvidence.model_validate(item)
            for item in effective_general_retriever.search(question, limit=3)
        ]
        if not passages:
            return _evidence_result(
                context,
                tool_name=GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME,
                answer="I could not find relevant guidance in the curated early-childhood knowledge base.",
                grounding_facts=[], citations=[], evidence_category="unknown",
            )
        return _evidence_result(
            context,
            tool_name=GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME,
            answer=" ".join(item.text for item in passages[:2]),
            grounding_facts=[item.text for item in passages],
            citations=[item.citation for item in passages],
            evidence_category="authoritative_fact",
        )

    return [
        StructuredTool.from_function(
            func=search_selected,
            name=SELECTED_SCHOOL_EVIDENCE_TOOL_NAME,
            description=(
                "Search official webpage evidence for exactly one authoritative selected "
                "school. Missing evidence means unavailable, not a negative fact."
            ),
            args_schema=EvidenceSearchToolRequest,
            infer_schema=False,
        ),
        StructuredTool.from_function(
            func=search_general,
            name=GENERAL_KNOWLEDGE_EVIDENCE_TOOL_NAME,
            description=(
                "Search authoritative general early-childhood guidance through the "
                "server-configured retrieval boundary."
            ),
            args_schema=EvidenceSearchToolRequest,
            infer_schema=False,
        ),
    ]
