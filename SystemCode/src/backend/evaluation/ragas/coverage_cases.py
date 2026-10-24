"""Evaluation-only conversation replay, controlled retrieval and exact checks."""

from copy import deepcopy
from unittest.mock import patch

from capture_dataset import capture, execution_case
from SystemCode.src.backend.agents import tools as agent_tools
from SystemCode.src.backend.agents.evaluation import (
    ConversationEvaluationCase, ExpectedProfileDelta, _expected_state_matches,
)


def validate_input(item):
    if set(item) != {"case_id", "user_input", "setup"}:
        raise ValueError("labels are forbidden in execution inputs")
    value = deepcopy(item)
    history = value["setup"]["conversation_history"]
    if not isinstance(history, list) or any(not isinstance(t, str) or not t.strip() for t in history):
        raise ValueError("conversation history must contain user setup turns")
    controls = value["setup"].pop("retrieval_control", None)
    if controls is not None and (set(controls) != {"mode", "school_id", "chunk_id"}
                                or controls["mode"] != "prepend_wrong_school"):
        raise ValueError("unsupported retrieval control")
    value["setup"]["conversation_history"] = []
    execution_case(value)
    return value, history, controls


def capture_conversation(service, item, model_factory, turn_capture=capture):
    value, history, controls = validate_input(item)
    turns = []
    original_retrieve = agent_tools.retrieve
    injected = []

    def controlled(index, school_id, question, *args, **kwargs):
        matches = original_retrieve(index, school_id, question, *args, **kwargs)
        wrong = original_retrieve(index, controls["school_id"], "transport", limit=100, min_relevance=0)
        wrong = [p for p in wrong if p["chunk_id"] == controls["chunk_id"]]
        if len(wrong) != 1:
            raise ValueError("controlled distractor not found in frozen index")
        injected.extend(deepcopy(wrong))
        return deepcopy(wrong) + matches

    for turn, message in enumerate([*history, item["user_input"]], 1):
        value["user_input"] = message
        # Controls affect only the measured answer, never conversation setup.
        if controls and turn == len(history) + 1:
            with patch.object(agent_tools, "retrieve", controlled):
                row = turn_capture(service, value, model_factory())
        else:
            row = turn_capture(service, value, model_factory())
        row["turn"] = turn
        turns.append(row)
        if row.get("execution_error"):
            break
        profile = row.get("agent_response", {}).get("profile")
        if not isinstance(profile, dict):
            row["execution_error"] = {"type": "MissingReturnedProfile"}
            break
        value["setup"]["profile"] = deepcopy(profile)
    result = deepcopy(turns[-1])
    result["turns"] = turns
    result["scored_turn"] = len(history) + 1
    result["controlled_retrievals"] = injected
    if len(turns) != len(history) + 1 or result.get("execution_error"):
        result.update(status="execution_error", execution_error={"type": "ConversationReplayFailure"},
                      response=None, retrieved_contexts=[])
    return result


def check_capture(case, row):
    """Exact properties use server state and frozen expectations; prose needs review."""
    if row.get("execution_error"):
        return {"execution": False}
    response = row.get("agent_response", {})
    citations = response.get("citations", [])
    checks = {}
    selected = case["setup"]["selected_school_ids"]
    if selected:
        school_citations = [c for c in citations if c.get("evidence_scope") == "school"]
        checks["school_citation_ownership"] = all(c.get("school_id") in selected for c in school_citations)
        if case.get("require_school_citation"):
            checks["school_citation_present"] = bool(school_citations)
    if case["category"] == "combined_evidence":
        checks["distinct_scopes"] = {"school", "general"} <= {c.get("evidence_scope") for c in citations}
    if case["category"] == "wrong_school_distractor":
        checks["distractor_exercised"] = bool(row.get("controlled_retrievals"))
        checks["wrong_school_filtered"] = all(
            p.get("school_id") in selected for p in row.get("passages", []) if p.get("school_id")
        )
    if "expected_profile_delta" in case:
        expectation = ConversationEvaluationCase(
            case_id=case["case_id"], sequence=1, conversation_id=case["case_id"], turn=1,
            message=case["user_input"], expected_intent="unused", expected_route_scope="clarification",
            expected_profile_delta=ExpectedProfileDelta.model_validate(case["expected_profile_delta"]),
        )
        checks["profile_delta"] = _expected_state_matches(response, expectation)
    if "expected_calculation" in case:
        # Compare amounts and direction in the final answer with the frozen
        # deterministic calculation, rather than grading arithmetic with an LLM.
        import re
        amounts = [float(a.replace(",", "")) for a in re.findall(r"\$([\d,]+(?:\.\d+)?)", row["response"])]
        expected = case["expected_calculation"]
        checks["exact_fee_transition"] = amounts == [expected["before"], expected["after"]]
        checks["calculation_tool"] = "run_what_if_scenario" in row.get("metadata", {}).get("tool_names", [])
        checks["profile_matches_controller"] = response.get("profile") == row.get("deterministic_response", {}).get("profile")
    return checks
