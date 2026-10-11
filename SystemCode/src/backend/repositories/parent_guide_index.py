"""Validated immutable parent-guide artifacts; no provider calls or rebuilding."""

import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import numpy as np

from SystemCode.src.backend.pipeline.parent_guide_chunking import ChunkingSettings, GuideChunk
from SystemCode.src.backend.pipeline.parent_guide_embeddings import EmbeddingSettings, validate_matrix


SCHEMA_VERSION = 1
BUILD_ID = re.compile(r"[0-9a-f]{32}")
HASH = re.compile(r"[0-9a-f]{64}")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Artifact timestamp requires a timezone.")


def validate_chunks(chunks: tuple[GuideChunk, ...], indexed_at: str):
    if not chunks:
        raise ValueError("Empty parent-guide index.")
    seen = set()
    for row, chunk in enumerate(chunks):
        if (not HASH.fullmatch(chunk.chunk_id) or chunk.chunk_id in seen
                or type(chunk.matrix_row) is not int or chunk.matrix_row != row
                or chunk.content_sha256 != sha256(chunk.embedding_text.encode("utf-8"))
                or chunk.chunk_id != sha256((chunk.mapping_id + "\n" + chunk.content_sha256).encode())
                or not chunk.mapping_id or not chunk.text.strip()
                or len(chunk.embedding_text) > 5000 or not chunk.embedding_text.endswith(chunk.text)
                or chunk.evidence_scope != "general" or chunk.review_status != "verified"
                or chunk.evidence_category not in ("authoritative_fact", "unknown")
                or chunk.indexed_at != indexed_at):
            raise ValueError("Invalid chunk ID, row, content or review metadata.")
        seen.add(chunk.chunk_id)
        document_path = Path(chunk.document_path)
        if document_path.is_absolute() or ".." in document_path.parts:
            raise ValueError("Invalid document-relative path.")
        url = urlparse(chunk.citation["url"])
        if (url.scheme != "https" or not url.netloc
                or chunk.citation["retrieved_at"] != chunk.source_verified_at):
            raise ValueError("Invalid chunk citation.")
        _timestamp(chunk.source_verified_at)


@dataclass(frozen=True)
class ParentGuideIndex:
    build_id: str
    chunks: tuple[GuideChunk, ...]
    embeddings: np.ndarray
    manifest: dict


def load_build(build_path: Path, *, expected_embedding: EmbeddingSettings | None = None,
               expected_chunking: ChunkingSettings | None = None) -> ParentGuideIndex:
    """Read bytes once, check their hashes, then decode with pickle disabled."""
    build_path = Path(build_path)
    if not BUILD_ID.fullmatch(build_path.name):
        raise ValueError("Invalid build identifier.")
    try:
        manifest = json.loads((build_path / "manifest.json").read_bytes())
        if (manifest["schema_version"] != SCHEMA_VERSION or manifest["build_id"] != build_path.name
                or manifest["dtype"] != "float32" or manifest["normalisation"] != "l2"
                or type(manifest["chunk_count"]) is not int or manifest["chunk_count"] < 1):
            raise ValueError("Unsupported index manifest.")
        _timestamp(manifest["indexed_at"])
        for field in ("source_sha256", "provenance_sha256"):
            if not HASH.fullmatch(manifest[field]):
                raise ValueError("Invalid source/provenance hash.")
        embedding = EmbeddingSettings(**manifest["embedding"])
        chunking = ChunkingSettings(**manifest["chunking"])
        if ((expected_embedding is not None and embedding != expected_embedding)
                or (expected_chunking is not None and chunking != expected_chunking)):
            raise ValueError("Incompatible index model or chunking settings.")
        artifacts = {}
        for name in ("chunks.json", "embeddings.npy", "summary.json"):
            data = (build_path / name).read_bytes()
            if sha256(data) != manifest["artifact_sha256"][name]:
                raise ValueError("Index artifact hash mismatch.")
            artifacts[name] = data
        records = json.loads(artifacts["chunks.json"])
        chunks = []
        for record in records:
            record["source_links"] = tuple(record["source_links"])
            record["required_qualifications"] = tuple(record["required_qualifications"])
            chunks.append(GuideChunk(**record))
        chunks = tuple(chunks)
        if len(chunks) != manifest["chunk_count"]:
            raise ValueError("Index chunk count mismatch.")
        validate_chunks(chunks, manifest["indexed_at"])
        matrix = np.load(io.BytesIO(artifacts["embeddings.npy"]), allow_pickle=False)
        validate_matrix(matrix, len(chunks), embedding.dimensions)
        summary = json.loads(artifacts["summary.json"])
        if (summary["build_id"] != build_path.name or summary["chunk_count"] != len(chunks)
                or any(type(summary[key]) is not int or summary[key] < 0
                       for key in ("embedded_count", "reused_count"))
                or summary["embedded_count"] + summary["reused_count"] != len(chunks)):
            raise ValueError("Invalid build summary.")
        matrix.flags.writeable = False
        return ParentGuideIndex(build_path.name, chunks, matrix, manifest)
    except (KeyError, TypeError, AttributeError, OverflowError, EOFError) as error:
        raise ValueError("Malformed parent-guide index.") from error


def load_active_index(vector_path: Path, **kwargs) -> ParentGuideIndex:
    vector_path = Path(vector_path)
    build_id = (vector_path / "CURRENT").read_text(encoding="ascii").strip()
    if not BUILD_ID.fullmatch(build_id):
        raise ValueError("Invalid active build identifier.")
    return load_build(vector_path / "builds" / build_id, **kwargs)
