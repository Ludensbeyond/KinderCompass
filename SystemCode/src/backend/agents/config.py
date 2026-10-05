"""Backend-only configuration for conversation agent capabilities."""

import os
from contextlib import contextmanager
from contextvars import ContextVar
from enum import Enum
from typing import Mapping, Optional


class WebRagAnswerMode(str, Enum):
    """Supported selected-school webpage answer implementations."""

    DETERMINISTIC = "deterministic"
    AGENT = "agent"


class ConversationAgentMode(str, Enum):
    """Supported full-conversation supervisor rollout modes."""

    DETERMINISTIC = "deterministic"
    SHADOW = "shadow"
    AGENT = "agent"


_AGENT_ENTRY_POINTS_DISABLED: ContextVar[bool] = ContextVar(
    "kindercompass_agent_entry_points_disabled", default=False,
)


@contextmanager
def disable_agent_entry_points():
    """Disable both graph entry points for one context-local fallback call."""

    token = _AGENT_ENTRY_POINTS_DISABLED.set(True)
    try:
        yield
    finally:
        _AGENT_ENTRY_POINTS_DISABLED.reset(token)


def get_web_rag_answer_mode(
    environ: Optional[Mapping[str, str]] = None,
) -> WebRagAnswerMode:
    """Read the answer mode, falling back safely for missing or invalid input."""

    if _AGENT_ENTRY_POINTS_DISABLED.get():
        return WebRagAnswerMode.DETERMINISTIC
    source = os.environ if environ is None else environ
    configured = source.get("WEB_RAG_ANSWER_MODE", "").strip().lower()
    try:
        return WebRagAnswerMode(configured)
    except ValueError:
        return WebRagAnswerMode.DETERMINISTIC


def get_conversation_agent_mode(
    environ: Optional[Mapping[str, str]] = None,
) -> ConversationAgentMode:
    """Read the supervisor mode, failing closed for missing or invalid input."""

    if _AGENT_ENTRY_POINTS_DISABLED.get():
        return ConversationAgentMode.DETERMINISTIC
    source = os.environ if environ is None else environ
    configured = source.get("CONVERSATION_AGENT_MODE", "").strip().lower()
    try:
        return ConversationAgentMode(configured)
    except ValueError:
        return ConversationAgentMode.DETERMINISTIC
