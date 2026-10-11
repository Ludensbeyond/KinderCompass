"""Explicit offline build; publish only after a fresh artifact validation."""

import io
import json
import os
import uuid
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from SystemCode.src.backend.pipeline.parent_guide_chunking import ChunkingSettings, chunk_parent_guide
from SystemCode.src.backend.pipeline.parent_guide_embeddings import EmbeddingProvider, embed_documents
from SystemCode.src.backend.repositories.parent_guide_index import (
    SCHEMA_VERSION, json_bytes, load_active_index, load_build, sha256, validate_chunks,
)


def _write_synced(path: Path, data: bytes):
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def build_parent_guide_index(vector_path: Path, provider: EmbeddingProvider, *,
                            settings: ChunkingSettings = ChunkingSettings(),
                            batch_size: int = 32, max_retries: int = 2,
                            timeout_seconds: float = 8.0) -> dict:
    """Reuse only validated compatible vectors; failed attempts never alter CURRENT.

    Concurrent builders write isolated directories; the last completed publisher
    wins. Incomplete directories are retained for inspection but never activated.
    """
    vector_path = Path(vector_path)
    provenance_bytes = (vector_path / "sources.json").read_bytes()
    provenance = json.loads(provenance_bytes)
    relative = Path(provenance["document_path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Invalid document-relative path.")
    source_bytes = (vector_path.parent / relative).read_bytes()
    indexed_at = datetime.now(timezone.utc).isoformat()
    chunks = tuple(replace(chunk, indexed_at=indexed_at) for chunk in
                   chunk_parent_guide(source_bytes.decode("utf-8"), provenance, settings))
    validate_chunks(chunks, indexed_at)
    reusable = {}
    try:
        prior = load_active_index(vector_path, expected_embedding=provider.settings,
                                  expected_chunking=settings)
    except (OSError, ValueError):
        pass  # Missing, corrupt or incompatible builds cannot supply reused vectors.
    else:
        reusable = {chunk.chunk_id: (chunk.content_sha256, prior.embeddings[chunk.matrix_row])
                    for chunk in prior.chunks}
    missing = [chunk for chunk in chunks if chunk.chunk_id not in reusable
               or reusable[chunk.chunk_id][0] != chunk.content_sha256]
    new_vectors = (embed_documents([chunk.embedding_text for chunk in missing], provider,
                                  batch_size=batch_size, max_retries=max_retries,
                                  timeout_seconds=timeout_seconds) if missing else None)
    vectors = {chunk.chunk_id: vector for chunk, vector in zip(missing, new_vectors)} if missing else {}
    matrix = np.stack([vectors[chunk.chunk_id] if chunk.chunk_id in vectors
                       else reusable[chunk.chunk_id][1] for chunk in chunks])
    build_id = uuid.uuid4().hex
    build_path = vector_path / "builds" / build_id
    build_path.mkdir(parents=True, exist_ok=False)
    summary = {"build_id": build_id, "chunk_count": len(chunks),
               "embedded_count": len(missing), "reused_count": len(chunks) - len(missing)}
    buffer = io.BytesIO()
    np.save(buffer, matrix, allow_pickle=False)
    artifacts = {"chunks.json": json_bytes([chunk.to_dict() for chunk in chunks]),
                 "embeddings.npy": buffer.getvalue(), "summary.json": json_bytes(summary)}
    manifest = {
        "schema_version": SCHEMA_VERSION, "build_id": build_id, "indexed_at": indexed_at,
        "source_sha256": sha256(source_bytes), "provenance_sha256": sha256(provenance_bytes),
        "chunking": asdict(settings), "embedding": asdict(provider.settings),
        "dtype": "float32", "normalisation": "l2", "chunk_count": len(chunks),
        "artifact_sha256": {name: sha256(data) for name, data in artifacts.items()},
    }
    for name, data in artifacts.items():
        _write_synced(build_path / name, data)
    _write_synced(build_path / "manifest.json", json_bytes(manifest))
    load_build(build_path, expected_embedding=provider.settings, expected_chunking=settings)
    pointer = vector_path / (".CURRENT-" + build_id)
    _write_synced(pointer, (build_id + "\n").encode("ascii"))
    os.replace(pointer, vector_path / "CURRENT")
    return summary
