"""Offline persistence, corruption, reuse and atomic publication contracts."""

import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from SystemCode.src.backend.pipeline.general_knowledge_config import DEFAULT_VECTOR_PATH, GeneralKnowledgeConfig, REPOSITORY_ROOT
from SystemCode.src.backend.pipeline.parent_guide_build import build_parent_guide_index
from SystemCode.src.backend.pipeline.parent_guide_chunking import ChunkingSettings, load_parent_guide_chunks
from SystemCode.src.backend.pipeline.parent_guide_embeddings import (
    EmbeddingBatch, EmbeddingSettings, OpenAIEmbeddingProvider, TransientEmbeddingError,
    embed_documents,
)
from SystemCode.src.backend.repositories.parent_guide_index import json_bytes, load_active_index, sha256


class FakeProvider:
    settings = EmbeddingSettings("test", "deterministic-v1", 4, "1")

    def __init__(self):
        self.calls = []

    def embed(self, texts, *, timeout_seconds):
        self.calls.append((tuple(texts), timeout_seconds))
        vectors = [[byte + 1 for byte in bytes.fromhex(sha256(text.encode()))[:4]] for text in texts]
        return EmbeddingBatch(vectors, self.settings.model)


class ParentGuideIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "parent_guide"
        self.path.mkdir()
        shutil.copy(DEFAULT_VECTOR_PATH / "sources.json", self.path / "sources.json")
        shutil.copy(DEFAULT_VECTOR_PATH.parent / "Singapore_Preschool_Parent_Guide.md", self.root)
        self.provider = FakeProvider()

    def build(self, **kwargs):
        return build_parent_guide_index(self.path, self.provider, **kwargs)

    def rewrite_artifact(self, name, data):
        build = self.path / "builds" / (self.path / "CURRENT").read_text().strip()
        (build / name).write_bytes(data)
        manifest = json.loads((build / "manifest.json").read_bytes())
        manifest["artifact_sha256"][name] = sha256(data)
        (build / "manifest.json").write_bytes(json_bytes(manifest))

    def test_build_reload_in_fresh_process_without_reembedding(self):
        summary = self.build(batch_size=5, timeout_seconds=3)
        self.assertEqual(summary["embedded_count"], 23)
        self.assertEqual(len(self.provider.calls), 5)
        self.assertTrue(all(len(texts) <= 5 and timeout == 3 for texts, timeout in self.provider.calls))
        index = load_active_index(self.path, expected_embedding=self.provider.settings)
        self.assertEqual(index.embeddings.shape, (23, 4))
        self.assertEqual(index.embeddings.dtype, np.float32)
        self.assertFalse(index.embeddings.flags.writeable)
        np.testing.assert_allclose(np.linalg.norm(index.embeddings, axis=1), 1, atol=1e-6)
        self.assertEqual(index.manifest["source_sha256"], sha256((self.root / "Singapore_Preschool_Parent_Guide.md").read_bytes()))
        self.assertEqual(index.manifest["provenance_sha256"], sha256((self.path / "sources.json").read_bytes()))
        for built, original in zip(index.chunks, load_parent_guide_chunks()):
            self.assertEqual(built.citation, original.citation)
            self.assertEqual(built.source_verified_at, original.source_verified_at)
            self.assertEqual(built.indexed_at, index.manifest["indexed_at"])
        code = "from SystemCode.src.backend.repositories.parent_guide_index import load_active_index; import sys; print(len(load_active_index(sys.argv[1]).chunks))"
        result = subprocess.run([os.sys.executable, "-c", code, str(self.path)], cwd=REPOSITORY_ROOT,
                                capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), "23")

    def test_unchanged_build_reuses_all_vectors_and_retains_previous_build(self):
        first = self.build()
        matrix = load_active_index(self.path).embeddings.copy()
        self.provider.embed = Mock(side_effect=AssertionError("Must reuse vectors"))
        second = self.build()
        self.assertEqual(second["reused_count"], 23)
        self.assertNotEqual(first["build_id"], second["build_id"])
        self.assertTrue((self.path / "builds" / first["build_id"]).is_dir())
        np.testing.assert_array_equal(load_active_index(self.path).embeddings, matrix)

    def test_changed_content_reembeds_only_that_chunk(self):
        self.build()
        provenance = json.loads((self.path / "sources.json").read_bytes())
        # Heading context is embedded: edit reviewed subsection text and repin source.
        source = self.root / "Singapore_Preschool_Parent_Guide.md"
        text = source.read_text()
        heading = load_parent_guide_chunks()[0].section_heading
        text = text.replace("## " + heading, "## " + heading + " revised", 1)
        source.write_text(text)
        provenance["document_sha256"] = sha256(text.encode())
        provenance["sections"][0]["heading"] = heading + " revised"
        (self.path / "sources.json").write_bytes(json_bytes(provenance))
        self.provider.calls.clear()
        summary = self.build()
        changed = sum(chunk.section_heading == heading for chunk in load_parent_guide_chunks())
        self.assertEqual(summary["embedded_count"], changed)
        self.assertEqual(summary["reused_count"], 23 - changed)

    def test_model_dimensions_version_and_chunking_mismatch_require_rebuild(self):
        self.build()
        for settings in (EmbeddingSettings("other", "deterministic-v1", 4, "1"),
                         EmbeddingSettings("test", "other-model", 4, "1"),
                         EmbeddingSettings("test", "deterministic-v1", 5, "1"),
                         EmbeddingSettings("test", "deterministic-v1", 4, "2")):
            with self.subTest(settings=settings), self.assertRaisesRegex(ValueError, "Incompatible"):
                load_active_index(self.path, expected_embedding=settings)
        with self.assertRaisesRegex(ValueError, "Incompatible"):
            load_active_index(self.path, expected_chunking=ChunkingSettings(target_characters=1700))
        self.provider.settings = EmbeddingSettings("test", "other-model", 4, "1")
        self.assertEqual(self.build()["embedded_count"], 23)
        self.assertEqual(self.build(settings=ChunkingSettings(target_characters=1700))["embedded_count"], 23)

    def test_provider_failure_leaves_active_index_usable(self):
        first = self.build()
        self.provider.settings = EmbeddingSettings("test", "changed", 4)
        self.provider.embed = Mock(side_effect=TransientEmbeddingError("failed"))
        with self.assertRaises(TransientEmbeddingError):
            self.build(max_retries=0)
        self.assertEqual(load_active_index(self.path).build_id, first["build_id"])

    def test_write_validation_and_publication_failures_keep_current(self):
        first = self.build()
        original = (self.path / "CURRENT").read_bytes()
        for target in ("_write_synced", "load_build", "os.replace"):
            with self.subTest(target=target):
                with patch("SystemCode.src.backend.pipeline.parent_guide_build." + target,
                           side_effect=OSError("simulated publication failure")):
                    with self.assertRaises(OSError):
                        self.build()
                self.assertEqual((self.path / "CURRENT").read_bytes(), original)
                self.assertEqual(load_active_index(self.path).build_id, first["build_id"])

    def test_artifact_hash_corruption_is_rejected_and_not_reused(self):
        self.build()
        build = self.path / "builds" / (self.path / "CURRENT").read_text().strip()
        for name in ("chunks.json", "embeddings.npy", "summary.json"):
            original = (build / name).read_bytes()
            (build / name).write_bytes(original + b"corruption")
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "hash mismatch"):
                load_active_index(self.path)
            (build / name).write_bytes(original)
        (build / "embeddings.npy").write_bytes(b"corrupt")
        self.assertEqual(self.build()["embedded_count"], 23)

    def test_invalid_ids_rows_and_counts_rejected_even_with_updated_hashes(self):
        self.build()
        original = [chunk.to_dict() for chunk in load_active_index(self.path).chunks]
        for key, value in (("chunk_id", ""), ("chunk_id", original[1]["chunk_id"]),
                           ("matrix_row", 1), ("content_sha256", "0" * 64),
                           ("review_status", "unverified")):
            records = copy.deepcopy(original)
            records[0][key] = value
            self.rewrite_artifact("chunks.json", json_bytes(records))
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                load_active_index(self.path)
        self.rewrite_artifact("chunks.json", json_bytes(original[:-1]))
        with self.assertRaisesRegex(ValueError, "count mismatch"):
            load_active_index(self.path)

    def test_empty_matrix_is_rejected_and_cannot_prevent_rebuild(self):
        self.build()
        self.rewrite_artifact("embeddings.npy", b"")
        with self.assertRaisesRegex(ValueError, "Malformed"):
            load_active_index(self.path)
        self.assertEqual(self.build()["embedded_count"], 23)

    def test_invalid_matrix_dimensions_norms_dtype_and_pickle_rejected(self):
        self.build()
        good = load_active_index(self.path).embeddings.copy()
        invalid = [good[:-1], good[:, :-1], good.astype(np.float64), good * 2,
                   np.zeros_like(good), good.astype(object)]
        for value in (float("nan"), float("inf")):
            matrix = good.copy()
            matrix[0, 0] = value
            invalid.append(matrix)
        for matrix in invalid:
            buffer = io.BytesIO()
            np.save(buffer, matrix, allow_pickle=True)
            self.rewrite_artifact("embeddings.npy", buffer.getvalue())
            with self.subTest(shape=matrix.shape, dtype=matrix.dtype), self.assertRaises(ValueError):
                load_active_index(self.path)

    def test_current_cannot_select_path_outside_builds(self):
        for pointer in ("../outside", "/tmp/outside", "", "bad", "a" * 32 + "/extra"):
            (self.path / "CURRENT").write_text(pointer)
            with self.subTest(pointer=pointer), self.assertRaises(ValueError):
                load_active_index(self.path)

    def test_manifest_schema_and_summary_counts_are_validated(self):
        self.build()
        build = self.path / "builds" / (self.path / "CURRENT").read_text().strip()
        original = json.loads((build / "manifest.json").read_bytes())
        for key, value in (("schema_version", 99), ("dtype", "float64"),
                           ("normalisation", "none"), ("chunk_count", 0),
                           ("indexed_at", "2026-10-09"), ("source_sha256", "bad")):
            manifest = copy.deepcopy(original)
            manifest[key] = value
            (build / "manifest.json").write_bytes(json_bytes(manifest))
            with self.subTest(key=key), self.assertRaises(ValueError):
                load_active_index(self.path)
        (build / "manifest.json").write_bytes(json_bytes(original))
        summary = json.loads((build / "summary.json").read_bytes())
        summary["reused_count"] = 23
        self.rewrite_artifact("summary.json", json_bytes(summary))
        with self.assertRaisesRegex(ValueError, "summary"):
            load_active_index(self.path)


class EmbeddingBatchTests(unittest.TestCase):
    def test_transient_errors_have_bounded_retries_and_backoff(self):
        provider = FakeProvider()
        provider.embed = Mock(side_effect=[TransientEmbeddingError(),
                                          EmbeddingBatch([[1, 2, 3, 4]], provider.settings.model)])
        sleep = Mock()
        embed_documents(["text"], provider, timeout_seconds=2, sleep=sleep)
        self.assertEqual(provider.embed.call_count, 2)
        sleep.assert_called_once_with(0.25)
        provider.embed = Mock(side_effect=TransientEmbeddingError())
        with self.assertRaises(TransientEmbeddingError):
            embed_documents(["text"], provider, max_retries=2, sleep=Mock())
        self.assertEqual(provider.embed.call_count, 3)

    def test_bad_provider_outputs_are_rejected_without_retry(self):
        for vectors, model in (([[0] * 4], "deterministic-v1"),
                               ([[float("nan")] * 4], "deterministic-v1"),
                               ([[1, 2]], "deterministic-v1"),
                               ([], "deterministic-v1"), ([[1] * 4], "other")):
            provider = FakeProvider()
            provider.embed = Mock(return_value=EmbeddingBatch(vectors, model))
            with self.subTest(vectors=vectors, model=model), self.assertRaises(ValueError):
                embed_documents(["text"], provider)
            self.assertEqual(provider.embed.call_count, 1)

    def test_invalid_execution_bounds_fail_before_calling_provider(self):
        provider = FakeProvider()
        for kwargs in ({"batch_size": 0}, {"batch_size": 129}, {"max_retries": 6},
                       {"timeout_seconds": float("nan")}, {"timeout_seconds": 31}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                embed_documents(["text"], provider, **kwargs)
        for texts in ([], [""], ["x" * 5001]):
            with self.assertRaises(ValueError):
                embed_documents(texts, provider)
        self.assertFalse(provider.calls)

    def test_openai_adapter_orders_results_and_supplies_model_dimensions_timeout(self):
        config = GeneralKnowledgeConfig()
        client = Mock()
        client.embeddings.create.return_value = SimpleNamespace(model=config.embedding_model, data=[
            SimpleNamespace(index=1, embedding=[2]), SimpleNamespace(index=0, embedding=[1])])
        provider = OpenAIEmbeddingProvider(config, client=client)
        result = provider.embed(["first", "second"], timeout_seconds=4)
        self.assertEqual(result.vectors, [[1], [2]])
        client.embeddings.create.assert_called_once_with(input=["first", "second"],
            model="text-embedding-3-small", dimensions=1536, encoding_format="float", timeout=4)
        client.embeddings.create.return_value.data[0].index = 0
        with self.assertRaisesRegex(ValueError, "indices"):
            provider.embed(["first", "second"], timeout_seconds=4)

    def test_openai_errors_are_sanitised_and_only_transient_errors_are_retryable(self):
        import httpx
        from openai import APIStatusError, APITimeoutError

        client = Mock()
        provider = OpenAIEmbeddingProvider(GeneralKnowledgeConfig(), client=client)
        request = httpx.Request("POST", "https://api.openai.com/v1/embeddings")
        failures = [(APITimeoutError(request=request), TransientEmbeddingError)]
        for status in (429, 500, 401):
            response = httpx.Response(status, request=request)
            failures.append((APIStatusError("sensitive provider details", response=response, body=None),
                             TransientEmbeddingError if status != 401 else RuntimeError))
        for error, expected in failures:
            client.embeddings.create.side_effect = error
            with self.subTest(error=type(error).__name__), self.assertRaises(expected) as caught:
                provider.embed(["text"], timeout_seconds=2)
            self.assertNotIn("sensitive", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
