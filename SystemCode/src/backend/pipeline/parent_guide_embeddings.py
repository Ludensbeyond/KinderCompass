"""Injectable document embeddings with bounded batches and transient retries."""

import math
import time
from dataclasses import dataclass
from typing import Protocol, Sequence

import numpy as np

from SystemCode.src.backend.pipeline.general_knowledge_config import GeneralKnowledgeConfig


@dataclass(frozen=True)
class EmbeddingSettings:
    provider: str
    model: str
    dimensions: int
    model_version: str | None = None

    def __post_init__(self):
        if (not self.provider or not self.model or type(self.dimensions) is not int
                or not 1 <= self.dimensions <= 65536
                or (self.model_version is not None and not self.model_version)):
            raise ValueError("Invalid embedding settings.")

    @classmethod
    def from_config(cls, config: GeneralKnowledgeConfig):
        return cls(config.embedding_provider, config.embedding_model, config.embedding_dimensions)


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: Sequence[Sequence[float]]
    model: str


class EmbeddingProvider(Protocol):
    settings: EmbeddingSettings

    def embed(self, texts: Sequence[str], *, timeout_seconds: float) -> EmbeddingBatch: ...


class TransientEmbeddingError(RuntimeError):
    """A timeout, connection failure, rate limit or temporary server failure."""


class OpenAIEmbeddingProvider:
    def __init__(self, config: GeneralKnowledgeConfig, *, client=None):
        self.settings = EmbeddingSettings.from_config(config)
        if self.settings.provider != "openai":
            raise ValueError("Unsupported embedding provider.")
        if client is None:
            from openai import OpenAI

            # The explicit batching helper owns retries; avoid nested SDK retries.
            client = OpenAI(timeout=config.timeout_seconds, max_retries=0)
        self.client = client

    def embed(self, texts: Sequence[str], *, timeout_seconds: float) -> EmbeddingBatch:
        from openai import APIConnectionError, APIStatusError, APITimeoutError

        try:
            response = self.client.embeddings.create(
                input=list(texts), model=self.settings.model,
                dimensions=self.settings.dimensions, encoding_format="float",
                timeout=timeout_seconds,
            )
        except (APIConnectionError, APITimeoutError):
            raise TransientEmbeddingError("Embedding connection or timeout failure.") from None
        except APIStatusError as error:
            if error.status_code in (408, 429) or error.status_code >= 500:
                raise TransientEmbeddingError("Temporary embedding provider failure.") from None
            raise RuntimeError("Embedding provider rejected the request.") from None
        entries = sorted(response.data, key=lambda entry: entry.index)
        if [entry.index for entry in entries] != list(range(len(texts))):
            raise ValueError("Invalid embedding response indices.")
        return EmbeddingBatch([entry.embedding for entry in entries], response.model)


def normalise_vectors(vectors, rows: int, dimensions: int) -> np.ndarray:
    """Reject invalid outputs before normalising to a finite float32 matrix."""
    matrix = np.asarray(vectors, dtype=np.float64)
    if matrix.shape != (rows, dimensions) or not np.isfinite(matrix).all():
        raise ValueError("Invalid embedding shape or non-finite values.")
    norms = np.linalg.norm(matrix, axis=1)
    if not np.isfinite(norms).all() or np.any(norms == 0):
        raise ValueError("Invalid zero or non-finite vector norm.")
    result = (matrix / norms[:, None]).astype(np.float32)
    validate_matrix(result, rows, dimensions)
    return result


def validate_matrix(matrix: np.ndarray, rows: int, dimensions: int):
    if (matrix.dtype != np.dtype("float32") or matrix.shape != (rows, dimensions)
            or not np.isfinite(matrix).all()):
        raise ValueError("Invalid persisted embedding matrix.")
    norms = np.linalg.norm(matrix.astype(np.float64), axis=1)
    if not np.allclose(norms, 1.0, atol=1e-5, rtol=0):
        raise ValueError("Embedding vectors must have unit length.")


def embed_documents(texts: Sequence[str], provider: EmbeddingProvider, *,
                    batch_size: int = 32, max_retries: int = 2,
                    timeout_seconds: float = 8.0, sleep=time.sleep) -> np.ndarray:
    if (type(batch_size) is not int or not 1 <= batch_size <= 128
            or type(max_retries) is not int or not 0 <= max_retries <= 5
            or not math.isfinite(timeout_seconds) or not 1 <= timeout_seconds <= 30):
        raise ValueError("Invalid embedding execution bounds.")
    if not texts or any(not isinstance(text, str) or not text.strip() or len(text) > 5000
                        for text in texts):
        raise ValueError("Invalid bounded embedding input.")
    matrices = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        for attempt in range(max_retries + 1):
            try:
                result = provider.embed(batch, timeout_seconds=timeout_seconds)
                break
            except TransientEmbeddingError:
                if attempt == max_retries:
                    raise
                sleep(min(0.25 * 2 ** attempt, 2.0))
        if result.model != provider.settings.model:
            raise ValueError("Embedding response model mismatch.")
        matrices.append(normalise_vectors(result.vectors, len(batch), provider.settings.dimensions))
    return np.concatenate(matrices)
