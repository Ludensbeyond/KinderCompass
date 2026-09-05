"""Backend-only configuration for conversation agent capabilities."""

import os
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


def get_web_rag_answer_mode(
    environ: Optional[Mapping[str, str]] = None,
) -> WebRagAnswerMode:
    """Read the answer mode, falling back safely for missing or invalid input."""

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

    source = os.environ if environ is None else environ
    configured = source.get("CONVERSATION_AGENT_MODE", "").strip().lower()
    try:
        return ConversationAgentMode(configured)
    except ValueError:
        return ConversationAgentMode.DETERMINISTIC
