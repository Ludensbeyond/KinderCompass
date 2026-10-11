"""Read-only synthetic baseline capture; no provider calls or persistent writes.

Run from the repository root with the documented backend PYTHONPATH. JSON goes
only to stdout; redirect deliberately to an output artifact when updating it.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage, ToolMessage

from SystemCode.src.backend.agents.contracts import CapabilityToolResult
from SystemCode.src.backend.agents.validation import run_conversation_supervisor
from SystemCode.src.backend.domain.models import PreferenceRequest, PreferenceResponse
from SystemCode.src.backend.services.preference_service import PreferenceService
from stage1.intent_router import classify_intent


class BaselineModel:
    """Script the first exposed capability; measure control flow, not quality."""

    def __init__(self, events):
        self.events = events
        self.tools = []

    def bind_tools(self, tools, **options):
        if tools and hasattr(tools[0], "name"):
            self.tools = tools
            self.events.append({"event": "bind_capabilities", "tools": [t.name for t in tools], "required": options.get("tool_choice") == "required"})
        return self

    def invoke(self, messages):
        self.events.append({"event": "model"})
        results = [CapabilityToolResult.model_validate_json(str(m.content)) for m in messages if isinstance(m, ToolMessage)]
        if results:
            return AIMessage(content=json.dumps({"answer": results[0].answer_candidate, "citation_ids": []}))
        return AIMessage(content="", tool_calls=[{"name": self.tools[0].name, "args": {}, "id": "baseline-call", "type": "tool_call"}])


def capture():
    schools = Mock()
    schools.catalogue_version = "synthetic-baseline-v1"
    schools.facet_summary.return_value = {}
    schools.get_many.return_value = []
    schools.all.return_value = []
    service = PreferenceService(schools, Mock(), Mock(), Path("."))
    traces = []
    profile = {}
    cases = [("greeting", "Hi", False), ("help", "What can you help me with?", False), ("mixed_preference_guidance", "I want Chinese, and what is Montessori?", False), ("importance_followup", "Make that required", True)]
    for case_id, message, carry in cases:
        events = []
        before = deepcopy(profile if carry else {})
        model = BaselineModel(events)

        def route(*args):
            events.append({"event": "semantic_routing"})
            result = classify_intent(*args)
            events.append({"event": "intent", "intent": result.intent})
            return result

        def run(context, tools, fallback):
            events.append({"event": "supervisor"})
            return run_conversation_supervisor(context, tools, fallback, model=model)

        def build(**kwargs):
            events.append({"event": "context_before_model"})
            return original_build(**kwargs)

        original_build = service.build_conversation_context
        with patch.dict("os.environ", {"CONVERSATION_AGENT_MODE": "agent", "GENERAL_KNOWLEDGE_RETRIEVAL_MODE": "curated", "OPENAI_INTENT_CLASSIFICATION_ENABLED": "false", "OPENAI_PREFERENCE_EXTRACTION_ENABLED": "false", "OPENAI_GROUNDED_EXPLANATIONS_ENABLED": "false", "OPENAI_WEB_RAG_ANSWERS_ENABLED": "false"}), patch("SystemCode.src.backend.services.preference_service.classify_intent", side_effect=route), patch.object(service, "build_conversation_context", side_effect=build), patch.object(service, "_resources", return_value=(None, None)), patch.object(service, "_run_conversation_agent", side_effect=run), patch.object(service, "_observe_conversation_agent"):
            response = service.handle(message=message, profile=before, selected_school_ids=[], eligible_school_ids=[], excluded_school_ids=[], family=None, home_postal_code=None)
        PreferenceResponse.model_validate(response)
        profile = deepcopy(response["profile"])
        traces.append({"case_id": case_id, "carries_previous_profile": carry, "events": events, "model_calls": sum(e["event"] == "model" for e in events), "profile_changed": profile != before, "chinese_preference_present": "Chinese" in json.dumps({key: profile.get(key) for key in ("hard_constraints", "preferences", "preference_items", "pending")}), "profile_keys": sorted(profile), "ready_to_search": response["ready_to_search"], "answer_method": response.get("answer_method"), "fallback_reason": response.get("fallback_reason")})
    schemas = {c.__name__: c.model_json_schema() for c in (PreferenceRequest, PreferenceResponse)}
    return {"schema_version": 1, "capture_kind": "synthetic_injected_model", "provider_calls": 0, "persistent_state_writes": 0, "preference_schema_sha256": hashlib.sha256(json.dumps(schemas, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), "traces": traces}


if __name__ == "__main__":
    print(json.dumps(capture(), indent=2))
