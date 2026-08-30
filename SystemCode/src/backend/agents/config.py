"""Configuration for the incremental selected-school evidence agent."""

import os
from enum import Enum
from typing import Mapping, Optional


class WebRagAnswerMode(str, Enum):
    """Supported selected-school webpage answer implementations."""

    DETERMINISTIC = "deterministic"
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
