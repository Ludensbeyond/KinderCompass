"""Lazy, backend-only model construction for agent capabilities."""

from __future__ import annotations

import math
import os
from enum import Enum
from typing import Any, Callable, Mapping, Optional

from .config import (
    ConversationAgentMode,
    WebRagAnswerMode,
    get_conversation_agent_mode,
    get_web_rag_answer_mode,
)


DEFAULT_WEB_RAG_MODEL = "gpt-4o-mini"
DEFAULT_WEB_RAG_TIMEOUT_SECONDS = 8.0
MIN_MODEL_TIMEOUT_SECONDS = 1.0
MAX_MODEL_TIMEOUT_SECONDS = 30.0


class ModelFactoryErrorCode(str, Enum):
    """Stable, non-sensitive reasons why an agent model was unavailable."""

    MISSING_CREDENTIALS = "missing_credentials"
    INVALID_CONFIGURATION = "invalid_configuration"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    INITIALIZATION_FAILED = "initialization_failed"


_SAFE_ERROR_MESSAGES = {
    ModelFactoryErrorCode.MISSING_CREDENTIALS: "Agent model credentials are unavailable.",
    ModelFactoryErrorCode.INVALID_CONFIGURATION: "Agent model configuration is invalid.",
    ModelFactoryErrorCode.DEPENDENCY_UNAVAILABLE: "Agent model dependency is unavailable.",
    ModelFactoryErrorCode.INITIALIZATION_FAILED: "Agent model initialization failed.",
}


class ModelFactoryError(RuntimeError):
    """Typed model-construction error that never embeds configuration values."""

    def __init__(self, code: ModelFactoryErrorCode) -> None:
        self.code = code
        super().__init__(_SAFE_ERROR_MESSAGES[code])


def _model_configuration(source: Mapping[str, str]) -> tuple[str, float, str]:
    model = source.get("OPENAI_WEB_RAG_MODEL", DEFAULT_WEB_RAG_MODEL).strip()
    if not model or len(model) > 128 or any(character.isspace() for character in model):
        raise ModelFactoryError(ModelFactoryErrorCode.INVALID_CONFIGURATION)

    configured_timeout = source.get(
        "OPENAI_WEB_RAG_TIMEOUT_SECONDS",
        str(DEFAULT_WEB_RAG_TIMEOUT_SECONDS),
    ).strip()
    try:
        timeout = float(configured_timeout)
    except (TypeError, ValueError):
        raise ModelFactoryError(ModelFactoryErrorCode.INVALID_CONFIGURATION) from None
    if not math.isfinite(timeout) or not MIN_MODEL_TIMEOUT_SECONDS <= timeout <= MAX_MODEL_TIMEOUT_SECONDS:
        raise ModelFactoryError(ModelFactoryErrorCode.INVALID_CONFIGURATION)

    api_key = source.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ModelFactoryError(ModelFactoryErrorCode.MISSING_CREDENTIALS)
    return model, timeout, api_key


def _create_configured_model(
    source: Mapping[str, str], client_factory: Optional[Callable[..., Any]],
) -> Any:
    model, timeout, api_key = _model_configuration(source)
    if client_factory is None:
        try:
            from langchain_openai import ChatOpenAI
        except (ImportError, ModuleNotFoundError):
            raise ModelFactoryError(ModelFactoryErrorCode.DEPENDENCY_UNAVAILABLE) from None
        client_factory = ChatOpenAI

    try:
        return client_factory(model=model, timeout=timeout, api_key=api_key)
    except Exception:
        raise ModelFactoryError(ModelFactoryErrorCode.INITIALIZATION_FAILED) from None


def create_agent_model(
    environ: Optional[Mapping[str, str]] = None,
    *,
    client_factory: Optional[Callable[..., Any]] = None,
) -> Optional[Any]:
    """Build the selected-school model only when agent mode is enabled.

    Returning ``None`` is the expected deterministic-mode behavior. Imports,
    credential reads, configuration validation, and client construction are all
    deferred until this function is called in agent mode.
    """

    source = os.environ if environ is None else environ
    if get_web_rag_answer_mode(source) is WebRagAnswerMode.DETERMINISTIC:
        return None

    return _create_configured_model(source, client_factory)


def create_conversation_agent_model(
    environ: Optional[Mapping[str, str]] = None,
    *,
    client_factory: Optional[Callable[..., Any]] = None,
) -> Optional[Any]:
    """Lazily build the shared model only for shadow or agent supervisor modes."""

    source = os.environ if environ is None else environ
    if get_conversation_agent_mode(source) is ConversationAgentMode.DETERMINISTIC:
        return None

    return _create_configured_model(source, client_factory)
