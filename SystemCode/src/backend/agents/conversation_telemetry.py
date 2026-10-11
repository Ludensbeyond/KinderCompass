"""Scalar-only new-flow telemetry; no model content or provider error text."""

from __future__ import annotations

import logging
import os
from time import monotonic

from SystemCode.src.backend.services.conversation_context_service import CAPABILITIES

LOGGER = logging.getLogger("kindercompass.llm_first")
# Standard USD / million tokens, official model pages checked 2026-10-10.
# Unknown models deliberately have no estimate. This is not a billing statement.
MODEL_RATES = {
    "gpt-4o-mini": (0.15, 0.075, 0.60),
    "gpt-4o-mini-2024-07-18": (0.15, 0.075, 0.60),
    "gpt-5.4-mini": (0.75, 0.075, 4.50),
}


class TurnTelemetry:
    def __init__(self, mode):
        self.mode = mode
        self.started = monotonic()
        self.model_calls = 0
        self.tool_names = []
        self.input_tokens = self.output_tokens = self.cached_tokens = 0
        self.usage_calls = 0
        self.comparison = None
        self.rates = MODEL_RATES.get(os.getenv("OPENAI_WEB_RAG_MODEL", "gpt-4o-mini").strip())

    def wrap(self, model):
        telemetry = self

        class ObservedModel:
            def __init__(self):
                self.delegate = model

            def bind_tools(self, tools):
                self.delegate = model.bind_tools(tools)
                return self

            def invoke(self, messages):
                telemetry.model_calls += 1
                response = self.delegate.invoke(messages)
                # Never log model-selected strings except registered capability names.
                for call in getattr(response, "tool_calls", ()):
                    name = call.get("name")
                    if name in CAPABILITIES and len(telemetry.tool_names) < 12:
                        telemetry.tool_names.append(name)
                usage = getattr(response, "usage_metadata", None)
                if isinstance(usage, dict):
                    incoming, outgoing = usage.get("input_tokens"), usage.get("output_tokens")
                    details = usage.get("input_token_details") or {}
                    cached = details.get("cache_read", 0) if isinstance(details, dict) else 0
                    if (type(incoming) is int and type(outgoing) is int and type(cached) is int
                            and 0 <= cached <= incoming and outgoing >= 0):
                        telemetry.input_tokens += incoming
                        telemetry.output_tokens += outgoing
                        telemetry.cached_tokens += cached
                        telemetry.usage_calls += 1
                return response

        return ObservedModel()

    def compare(self, legacy, candidate):
        if legacy is not None:
            self.comparison = {
                "profile_matches": legacy.get("profile") == candidate.get("profile"),
                "readiness_matches": legacy.get("ready_to_search") == candidate.get("ready_to_search"),
                "citations_match": legacy.get("citations", []) == candidate.get("citations", []),
            }

    def emit(self, response):
        import json
        reason = getattr(response, "failure_reason", None)
        # Reasons originate from the new-flow fixed exception categories only.
        allowed = {"elapsed_limit", "context_limit", "output_limit", "model_limit", "tool_limit",
                   "invalid_model_message", "invalid_tool_call", "invalid_tool_arguments",
                   "invalid_answer", "response_validation", "repair_tool_call", "context_mismatch",
                   "execution_error", "response_error"}
        complete_usage = self.model_calls > 0 and self.usage_calls == self.model_calls
        cost = None
        if self.rates and complete_usage:
            incoming, cached, outgoing = self.rates
            cost = ((self.input_tokens - self.cached_tokens) * incoming
                    + self.cached_tokens * cached + self.output_tokens * outgoing) / 1_000_000
        event = {
            "schema_version": 1, "mode": self.mode,
            "elapsed_ms": round((monotonic() - self.started) * 1000, 3),
            "model_calls": self.model_calls, "tool_names": self.tool_names,
            "executed_tool_calls": getattr(response, "tool_calls", 0),
            "validation_succeeded": getattr(response, "status", None) == "ok",
            "failure_reason": reason if reason in allowed else ("request_or_commit_failure" if response is None else None),
            "input_tokens": self.input_tokens, "cached_input_tokens": self.cached_tokens,
            "output_tokens": self.output_tokens, "usage_complete": complete_usage,
            "estimated_cost_usd": cost, "comparison": self.comparison,
        }
        try:
            LOGGER.info("llm_first_observation %s", json.dumps(event, allow_nan=False))
        except Exception:
            pass
