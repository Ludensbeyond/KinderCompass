"""Mechanical grounding for model-authored replies; no answer substitution."""

import asyncio
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .contracts import AnswerText, Identifier, InitialConversationContext, PublicCitation
from .structured_contracts import StructuredToolResult
from .conversation_loop import ConversationLoopError, LoopLimits, run_conversation_loop
from ..services.conversation_tool_service import ConversationToolService


FINAL_RESPONSE_PROMPT = """Return final content as JSON with answer (at most 800
characters), kind (conversation, clarification, grounded, or evidence_gap),
and claims (a list). Each factual claim has span (the exact answer substring),
result_id, path (a JSON pointer into that result, such as /data/records/0/fee),
value (the exact scalar from that path), school_id (or null), citation_ids (list).
Include claims for facts, numerical values and preference-change acknowledgements.
Grounded replies require claims. Conversation/clarification may use zero claims
for greetings, capabilities and questions, never unsupported domain assertions.
For evidence gaps, support the explanation with the result's /status; absence of
evidence is not absence of a school attribute. Use [citation_id] markers for
retrieved evidence and include those IDs in the corresponding claim. Paraphrase
naturally; do not copy passages or fabricate values, sources or citations. Do
not round numbers: report the supplied numeric value. Claims for school records
must use the school_id of that record and explicitly name that school in the
span. Claims for retrieved passages must cite that passage's chunk_id. During
repair, return corrected final JSON using existing results; do not call tools.
Use actual result IDs and scalar paths exactly as returned, not schematic examples.
A reply combining guidance with a preference question uses kind grounded and
retains its guidance claims and [citation_id] markers. Do not remove claims or
citations by relabeling domain guidance as conversation during repair.
Claims should have short spans for individual facts; a span reporting two amounts
cannot be supported by one amount. Numeric questions (including postal-code length)
must avoid unsupported numbers: ask for 'your home postal code'. For needs_input,
clarify missing input without claiming a completed change. Use /status to support
an evidence gap, with school_id null since status belongs to the whole result.
Never explain unsupported domain facts even with a disclaimer. If guidance is
unavailable, acknowledge that gap and continue any supported preference work.
Each school fact MUST be its own short sentence repeating the FULL repository
school name. Set span to that exact full sentence, including any citation marker.
Never use 'its', 'both', shortened names, or a shared subject across claims.
Do not include extra numeric facts in that sentence. For example, given a fee
result for Example School, write 'Example School has a base fee of $900.' with
span exactly that sentence, value 900, path /data/records/0/facts/base_fee.
For a second fact repeat 'Example School' in a separate sentence with its own
claim. A passage sentence must include [chunk_id] INSIDE its claim span.
If you revise an answer, revise every span to an EXACT substring of the revised
answer, not a hypothetical sentence. Use numeric JSON values for numeric facts.
For comparison, report each school's facts separately; no combined 'both' claim.
Do not report age, scenario income or limits without their own scalar support.
Ask the pending required/preferred question in mixed guidance/preference replies.
For acknowledgements of UNCHANGED current preferences, use result_id context:current,
path /data/profile/... and the exact scalar from initial context. This supports
remembered state only, never school facts or proposed mutations. A changed state
must reference a successful mutation tool result. If a pending contradiction is
resolved, actually call reset_continue_preferences; wording alone does not resolve it.
"""


class ResponseClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    span: str = Field(min_length=1, max_length=800)
    result_id: Identifier
    path: str = Field(min_length=1, max_length=500)
    value: str | bool | int | float | None
    school_id: Identifier | None = None
    citation_ids: list[Identifier] = Field(default_factory=list, max_length=15)


class ModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    answer: AnswerText
    kind: Literal["conversation", "clarification", "grounded", "evidence_gap"]
    claims: list[ResponseClaim] = Field(default_factory=list, max_length=30)


class ResponseValidationError(ValueError):
    """Feedback consists only of fixed categories, never source or provider text."""


REPAIR_GUIDANCE = {
    "missing_pending_question": "A staged decision remains unresolved. Ask required or preferred for pending strength; ask keep existing or use incoming for a conflict. Include this question alongside supported guidance.",
    "wrong_reported_number": "Split claims into shorter exact spans so each span contains only its supported number. Remove other numbers from that span and support them separately.",
    "invalid_response_kind": "Use grounded when claims are present; conversation and clarification require an empty claims list.",
    "support_must_be_scalar": "Index list values, e.g. /data/records/0/facts/care_levels/0, not /data/records/0/facts/care_levels.",
    "invalid_response_structure": "Return valid JSON; claim value must be a scalar, never an array/object.",
    "missing_school_attribution": "Repeat the full school name inside every school claim span, including estimate warnings. Rewrite both answer and spans.",
    "cross_school_attribution": "Use school_id null for result-level status or missing_evidence_school_ids scalars. Do not cite another school's passage for a gap.",
    "missing_citation_marker": "Include the [citation_id] marker inside the exact claim span.",
    "unknown_claim_support": "Use actual result IDs and exact answer substrings. Never use profile or context as result_id.",
    "unsupported_reported_number": "Remove unsupported numbers, even in refusals, questions and acknowledgements. You can acknowledge keeping the limit without repeating its number.",
    "unsupported_result_status": "Use /status for missing-input/evidence gaps; staged_profile scalars are allowed only for mutation results.",
}


_NUMBER = re.compile(r"(?<![\w])[-+]?\d+(?:,\d{3})*(?:\.\d+)?(?![\w])")
_CITATION = re.compile(r"\[([^\[\]\n]+)\]")


def _numbers(text: str) -> list[Decimal]:
    return [Decimal(m.group().replace(",", "")) for m in _NUMBER.finditer(text)]


def _resolve(result: StructuredToolResult, path: str):
    """Resolve a scalar and nearest containing school/passage, never model data."""
    node: Any = result.model_dump(mode="json")
    school_id = chunk_id = None
    if not (path == "/status" or path.startswith("/data/")):
        raise ResponseValidationError("invalid_support_path")
    for token in path[1:].split("/"):
        if isinstance(node, dict):
            school_id = node.get("school_id", school_id)
            chunk_id = node.get("chunk_id", chunk_id)
            node = node[token.replace("~1", "/").replace("~0", "~")]
        elif isinstance(node, list) and token.isdigit():
            node = node[int(token)]
        else:
            raise ResponseValidationError("invalid_support_path")
    if isinstance(node, (dict, list)):
        raise ResponseValidationError("support_must_be_scalar")
    return node, school_id, chunk_id


def validate_response(content: str, results: tuple[StructuredToolResult, ...],
                      context: InitialConversationContext) -> ModelResponse:
    """Check typed support/value/attribution/citations, not semantic entailment."""
    try:
        response = ModelResponse.model_validate(json.loads(content))
    except Exception:
        raise ResponseValidationError("invalid_response_structure") from None
    by_id = {r.result_id: r for r in results}
    from ..pipeline.stage1.preference_schema import sync_preference_schema
    current = sync_preference_schema(context.profile)
    # The public profile can contain legacy conversational metadata; expose only
    # validated preference values here, never arbitrary client-supplied facts.
    preference_snapshot = {
        "hard_constraints": {k: v for k, v in current.get("hard_constraints", {}).items()
                             if k in {"language", "level", "max_distance_km"}},
        "preference_items": current.get("preference_items", []),
        "unsupported_preferences": current.get("unsupported_preferences", []),
    }
    by_id["context:current"] = StructuredToolResult(
        result_id="context:current", tool_name="update_preferences", status="ok",
        data={"profile": preference_snapshot}, catalogue_version=context.catalogue_version, state_revision=0)
    citations = {}
    names = {s.school_id: s.name for s in context.selected_schools}
    for result in results:
        for passage in result.data.get("passages", []):
            if passage.get("school_id") and passage.get("school_name"):
                names[passage["school_id"]] = passage["school_name"]
        for record in result.data.get("records", []):
            if record.get("school_id") and (record.get("name") or record.get("school_name")):
                names[record["school_id"]] = record.get("name") or record["school_name"]
        for citation in result.citations:
            previous = citations.get(citation.citation_id)
            if previous and previous != citation:
                raise ResponseValidationError("conflicting_citation")
            citations[citation.citation_id] = citation
    if response.kind == "grounded" and not response.claims:
        raise ResponseValidationError("missing_claim_support")
    staged = next((r.data.get("staged_profile") for r in reversed(results)
                   if "staged_profile" in r.data), current)
    if staged and any(staged.get(k) for k in ("pending", "pending_contradiction", "pending_relaxation")):
        if "?" not in response.answer:
            raise ResponseValidationError("missing_pending_question")
    if response.kind in {"conversation", "clarification"} and response.claims:
        raise ResponseValidationError("invalid_response_kind")
    if response.kind == "evidence_gap" and not any(
        c.path == "/status" and c.value in {"no_evidence", "needs_input", "unavailable"}
        for c in response.claims
    ):
        raise ResponseValidationError("missing_gap_support")
    answer_markers = _CITATION.findall(response.answer)
    supported_markers: set[str] = set()
    covered_numbers: list[Decimal] = []
    span_numbers: dict[str, tuple[list[Decimal], list[Decimal]]] = {}
    latest_revision = max((r.state_revision for r in results), default=0)
    for claim in response.claims:
        if claim.span not in response.answer or claim.result_id not in by_id:
            raise ResponseValidationError("unknown_claim_support")
        result = by_id[claim.result_id]
        try:
            value, school_id, chunk_id = _resolve(result, claim.path)
        except (KeyError, IndexError):
            raise ResponseValidationError("invalid_support_path") from None
        if type(value) is not type(claim.value) or value != claim.value:
            # JSON distinguishes booleans from numbers; int/float equivalence is safe.
            if not (type(value) in (int, float) and type(claim.value) in (int, float)
                    and Decimal(str(value)) == Decimal(str(claim.value))):
                raise ResponseValidationError("wrong_claim_value")
        staged_support = (result.status == "needs_input" and result.tool_name in {
            "update_preferences", "reset_continue_preferences"} and
            claim.path.startswith(("/data/staged_profile/", "/data/unresolved_decisions/")))
        if result.status != "ok" and claim.path != "/status" and not staged_support:
            raise ResponseValidationError("unsupported_result_status")
        if result.tool_name in {"update_preferences", "reset_continue_preferences",
                                "search_rank_compare_schools", "calculate_fees_scenario"} and result.state_revision != latest_revision:
            raise ResponseValidationError("stale_state_claim")
        if school_id != claim.school_id:
            raise ResponseValidationError("cross_school_attribution")
        if school_id:
            name = names.get(school_id)
            if not name or name.casefold() not in claim.span.casefold():
                raise ResponseValidationError("missing_school_attribution")
            if any(other != school_id and other_name.casefold() in claim.span.casefold()
                   for other, other_name in names.items() if other_name != name):
                raise ResponseValidationError("cross_school_attribution")
        for citation_id in claim.citation_ids:
            citation = citations.get(citation_id)
            if citation is None or citation not in result.citations:
                raise ResponseValidationError("invented_citation")
            if citation.school_id != school_id:
                raise ResponseValidationError("cross_school_citation")
            if f"[{citation_id}]" not in claim.span:
                raise ResponseValidationError("missing_citation_marker")
            supported_markers.add(citation_id)
        if chunk_id and chunk_id not in claim.citation_ids:
            raise ResponseValidationError("missing_passage_citation")
        clean_span = _CITATION.sub("", claim.span)
        for name in names.values():
            clean_span = clean_span.replace(name, "")
        numbers = _numbers(clean_span)
        expected = _numbers(str(value)) if type(value) in (str, int, float) else []
        # Several scalar claims may support one natural sentence. Validate its
        # numbers against their combined values after every claim is validated.
        group = span_numbers.setdefault(claim.span, (numbers, []))
        group[1].extend(expected)
    for numbers, expected in span_numbers.values():
        if any(number not in expected for number in numbers):
            raise ResponseValidationError("wrong_reported_number")
        covered_numbers.extend(numbers)
    if set(answer_markers) != supported_markers:
        raise ResponseValidationError("unsupported_citation_marker")
    clean_answer = _CITATION.sub("", response.answer)
    for name in names.values():
        clean_answer = clean_answer.replace(name, "")
    from collections import Counter
    if Counter(_numbers(clean_answer)) - Counter(covered_numbers):
        raise ResponseValidationError("unsupported_reported_number")
    return response


SERVICE_ERROR = "The conversation service is unavailable. Please try again."


@dataclass(frozen=True)
class ConversationResponse:
    answer: str
    status: Literal["ok", "unavailable"]
    profile: dict | None = None
    citations: tuple[PublicCitation, ...] = ()
    claims: tuple[ResponseClaim, ...] = ()
    model_calls: int = 0
    tool_calls: int = 0
    failure_reason: str | None = None


async def run_validated_conversation(context: InitialConversationContext,
                                     tools: ConversationToolService, *, model: Any,
                                     limits: LoopLimits | None = None,
                                     shadow: bool = False, **kwargs) -> ConversationResponse:
    """Export once after validation; persistence/HTTP/history remain Step 6."""
    validated: list[ModelResponse] = []
    def validate(content, results):
        validated.append(validate_response(content, results, context))
    try:
        candidate = await run_conversation_loop(
            context, tools, model=model, limits=limits, final_validator=validate,
            final_prompt=FINAL_RESPONSE_PROMPT, **kwargs,
        )
        response = validated[-1]
        profile = tools.export_validated_state(response_validated=True, shadow=shadow)
        used = {c for claim in response.claims for c in claim.citation_ids}
        citations = {c.citation_id: c for r in candidate.results for c in r.citations if c.citation_id in used}
        return ConversationResponse(response.answer, "ok", profile,
                                    tuple(citations.values()), tuple(response.claims),
                                    candidate.model_calls, candidate.tool_calls)
    except asyncio.CancelledError:
        tools.abort()
        raise
    except Exception as error:
        tools.abort()
        reason = error.reason if isinstance(error, ConversationLoopError) else "response_error"
        return ConversationResponse(SERVICE_ERROR, "unavailable", failure_reason=reason)
