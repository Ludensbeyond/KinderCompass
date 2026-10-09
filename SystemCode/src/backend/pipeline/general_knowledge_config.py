"""Configuration reserved for the opt-in parent-guide retrieval extension.

Reading configuration performs no provider calls or index loading. Runtime
construction and wiring are intentionally deferred to the later plan steps.
"""

import math
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_VECTOR_PATH = REPOSITORY_ROOT / "SystemCode/data/vectors/parent_guide"


class GeneralKnowledgeRetrievalMode(str, Enum):
    CURATED = "curated"
    LEXICAL = "lexical"
    VECTOR = "vector"


@dataclass(frozen=True)
class GeneralKnowledgeConfig:
    mode: GeneralKnowledgeRetrievalMode = GeneralKnowledgeRetrievalMode.CURATED
    vector_path: Path = DEFAULT_VECTOR_PATH
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    timeout_seconds: float = 8.0
    max_query_characters: int = 2000


def get_general_knowledge_config(
    environ: Mapping[str, str] | None = None,
) -> GeneralKnowledgeConfig:
    """Parse server configuration without reading or storing credentials.

    Missing, blank or unknown modes remain curated. Invalid provider/model or
    execution bounds raise a value-free error for the future fallback boundary.
    Relative paths resolve against the repository, independent of worker cwd.
    """
    source = os.environ if environ is None else environ
    try:
        mode = GeneralKnowledgeRetrievalMode(
            source.get("GENERAL_KNOWLEDGE_RETRIEVAL_MODE", "").strip().lower(),
        )
    except ValueError:
        mode = GeneralKnowledgeRetrievalMode.CURATED
    provider = source.get("GENERAL_KNOWLEDGE_EMBEDDING_PROVIDER", "openai").strip().lower()
    model = source.get("GENERAL_KNOWLEDGE_EMBEDDING_MODEL", "text-embedding-3-small").strip()
    try:
        dimensions = int(source.get("GENERAL_KNOWLEDGE_EMBEDDING_DIMENSIONS", "1536"))
        timeout = float(source.get("GENERAL_KNOWLEDGE_TIMEOUT_SECONDS", "8"))
        query_length = int(source.get("GENERAL_KNOWLEDGE_MAX_QUERY_CHARACTERS", "2000"))
    except (TypeError, ValueError):
        raise ValueError("Invalid general knowledge configuration.") from None
    if (
        provider != "openai"
        or model != "text-embedding-3-small"
        or dimensions != 1536
        or not math.isfinite(timeout)
        or not 1 <= timeout <= 30
        or not 1 <= query_length <= 2000
    ):
        raise ValueError("Invalid general knowledge configuration.")
    configured_path = source.get("GENERAL_KNOWLEDGE_VECTOR_PATH", "").strip()
    path = Path(configured_path).expanduser() if configured_path else DEFAULT_VECTOR_PATH
    if not path.is_absolute():
        path = REPOSITORY_ROOT / path
    return GeneralKnowledgeConfig(mode, path.resolve(), provider, model, dimensions, timeout, query_length)
