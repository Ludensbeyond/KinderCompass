"""Standalone query ranking, bounds, periods and ordered failure recovery."""

from dataclasses import replace
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np

from SystemCode.src.backend.agents.tools import CuratedGeneralKnowledgeRetriever
from SystemCode.src.backend.pipeline.general_knowledge_config import (
    DEFAULT_VECTOR_PATH, GeneralKnowledgeConfig, GeneralKnowledgeRetrievalMode,
)
from SystemCode.src.backend.pipeline.parent_guide_embeddings import EmbeddingBatch, EmbeddingSettings
from SystemCode.src.backend.pipeline.parent_guide_retrieval import ParentGuideRetriever
from SystemCode.src.backend.repositories.parent_guide_index import load_active_index
from SystemCode.src.backend.scripts.query_parent_guide import main


LABELLED = [
    ("What is Montessori?", "montessori-emphasis"),
    ("What is SPARK?", "spark-quality"),
    ("How do subsidy thresholds change in 2027?", "additional-subsidy-2027-table"),
    ("What are childcare subsidy amounts in 2026?", "additional-subsidy-2026-table"),
    ("Does the childcare work exception also apply to infant care?", "basic-subsidy-and-exception"),
    ("What is CDA used for?", "cda-current-benefits"),
    ("What are AOP fee caps in 2026?", "aop-2026-fees"),
    ("How does EIPIC support children?", "eipic-role"),
]
NEGATIVE = ["What is the weather tomorrow?", "How do I repair my bicycle?",
            "Write a recipe for chocolate cake", "Who won the football match?",
            "Can parents watch the CCTV livestream?", "Does a waitlist guarantee a place?"]


class ParentGuideRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.config = GeneralKnowledgeConfig(mode=GeneralKnowledgeRetrievalMode.VECTOR)
        self.index = load_active_index(DEFAULT_VECTOR_PATH)
        self.provider = Mock(settings=EmbeddingSettings.from_config(self.config))

    def query_vector(self, mapping):
        row = next(i for i, c in enumerate(self.index.chunks) if c.mapping_id == mapping)
        self.provider.embed.return_value = EmbeddingBatch([self.index.embeddings[row]], self.provider.settings.model)

    def mappings(self, retriever, matches):
        return [next(c.mapping_id for c in retriever.chunks if c.chunk_id == m.chunk_id) for m in matches]

    def test_lexical_labelled_questions_and_unavailable(self):
        r = ParentGuideRetriever(replace(self.config, mode=GeneralKnowledgeRetrievalMode.LEXICAL), provider=self.provider)
        for question, expected in LABELLED:
            with self.subTest(question=question):
                self.assertIn(expected, self.mappings(r, r.search(question)))
                self.assertEqual(r.status.mode, "lexical")
        for question in NEGATIVE:
            with self.subTest(question=question):
                self.assertEqual(r.search(question), [])
        self.provider.embed.assert_not_called()

    def test_cosine_ranking_typed_citations_and_three_result_bound(self):
        self.query_vector("montessori-emphasis")
        r = ParentGuideRetriever(self.config, provider=self.provider)
        matches = r.search("What is Montessori?", limit=100)
        self.assertLessEqual(len(matches), 3)
        self.assertEqual(self.mappings(r, matches)[0], "montessori-emphasis")
        self.assertEqual(r.status.mode, "vector")
        chunk = next(c for c in r.chunks if c.mapping_id == "montessori-emphasis")
        self.assertEqual(matches[0].citation.url, chunk.citation["url"])
        self.assertEqual(matches[0].citation.retrieved_at.isoformat(), chunk.source_verified_at)
        self.assertEqual(matches[0].evidence_category, chunk.evidence_category)
        self.assertIn(chunk.text, matches[0].text)
        self.provider.embed.assert_called_once_with(["What is Montessori?"], timeout_seconds=8.0)

    def test_load_once_and_embed_only_questions(self):
        self.query_vector("spark-quality")
        with patch("SystemCode.src.backend.pipeline.parent_guide_retrieval.load_active_index", wraps=load_active_index) as loader:
            r = ParentGuideRetriever(self.config, provider=self.provider)
            r.search("What is SPARK?")
            r.search("Explain SPARK")
        loader.assert_called_once()
        self.assertEqual(self.provider.embed.call_count, 2)

    def test_explicit_dates_and_topics_filter_before_ranking(self):
        self.query_vector("additional-subsidy-2026-table")
        r = ParentGuideRetriever(self.config, provider=self.provider)
        matches = r.search("How do subsidy thresholds change in 2027?")
        ids = self.mappings(r, matches)
        self.assertIn("additional-subsidy-2027-table", ids)
        self.assertNotIn("additional-subsidy-2026-table", ids)
        self.assertIn("Policy period: 2027", matches[ids.index("additional-subsidy-2027-table")].text)
        self.query_vector("additional-subsidy-2027-table")
        matches = r.search("subsidy amounts", year=2026, topic="additional-subsidy-2026-table")
        self.assertEqual(self.mappings(r, matches), ["additional-subsidy-2026-table"])

    def test_ambiguous_question_preserves_both_labelled_periods(self):
        self.query_vector("additional-subsidy-2026-table")
        r = ParentGuideRetriever(self.config, provider=self.provider)
        matches = r.search("What are the Additional Subsidy amounts?")
        ids = self.mappings(r, matches)
        for mapping, period in [("additional-subsidy-2026-table", "2026"), ("additional-subsidy-2027-table", "2027")]:
            self.assertIn(mapping, ids)
            self.assertIn("Policy period: " + period, matches[ids.index(mapping)].text)

    def test_low_relevance_rejects_nearest_neighbour_then_uses_lexical(self):
        # Orthogonal query makes every cosine score zero without fabricating a hit.
        _, _, vh = np.linalg.svd(self.index.embeddings, full_matrices=True)
        self.provider.embed.return_value = EmbeddingBatch([vh[-1]], self.provider.settings.model)
        r = ParentGuideRetriever(self.config, provider=self.provider)
        self.assertEqual(r.search("What is the weather tomorrow?"), [])
        self.assertEqual(r.status.failure_category, "low_relevance")
        self.assertEqual(self.mappings(r, r.search("What is Montessori?")), ["montessori-emphasis"])
        self.assertEqual(r.status.mode, "lexical")

    def test_timeout_invalid_outputs_and_model_mismatches_use_lexical(self):
        r = ParentGuideRetriever(self.config, provider=self.provider)
        failures = [TimeoutError("private details"), EmbeddingBatch([[0] * 1536], self.provider.settings.model),
                    EmbeddingBatch([[1]], self.provider.settings.model), EmbeddingBatch([[1] * 1536], "wrong")]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                self.provider.embed.side_effect = failure if isinstance(failure, Exception) else None
                self.provider.embed.return_value = failure
                self.assertEqual(self.mappings(r, r.search("What is Montessori?")), ["montessori-emphasis"])
                self.assertEqual(r.status.failure_category, "embedding_unavailable")
        self.provider.settings = EmbeddingSettings("openai", "wrong", 1536)
        self.provider.embed.reset_mock()
        self.assertTrue(r.search("What is Montessori?"))
        self.provider.embed.assert_not_called()

    def test_missing_corrupt_and_incompatible_artifacts_recover_from_reviewed_source(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "parent_guide"
            shutil.copytree(DEFAULT_VECTOR_PATH, path)
            shutil.copy(DEFAULT_VECTOR_PATH.parent / "Singapore_Preschool_Parent_Guide.md", Path(temp))
            configs = [replace(self.config, vector_path=path, embedding_model="wrong")]
            build = path / "builds" / (path / "CURRENT").read_text().strip()
            for action in ("incompatible", "corrupt", "missing"):
                if action == "corrupt":
                    (build / "embeddings.npy").write_bytes(b"corrupt")
                if action == "missing":
                    (path / "CURRENT").unlink()
                config = configs[0] if action == "incompatible" else replace(self.config, vector_path=path)
                r = ParentGuideRetriever(config, provider=self.provider)
                self.assertEqual(self.mappings(r, r.search("What is Montessori?")), ["montessori-emphasis"])
                self.assertEqual(r.status.failure_category, "index_unavailable")
            self.provider.embed.assert_not_called()

    def test_curated_last_fallback_and_constraints_are_not_undone(self):
        curated = CuratedGeneralKnowledgeRetriever({"chunks": [{
            "chunk_id": "curated:test", "text": "Waldorf education supports creative play.",
            "source_url": "https://example.org/waldorf", "title": "Waldorf",
            "retrieved_at": "2026-10-09T00:00:00Z",
        }]})
        r = ParentGuideRetriever(replace(self.config, mode=GeneralKnowledgeRetrievalMode.LEXICAL), curated=curated)
        self.assertEqual(r.search("What is Waldorf?")[0].chunk_id, "curated:test")
        self.assertEqual(r.status.mode, "curated")
        self.assertEqual(r.search("What is Waldorf in 2027?"), [])
        r = ParentGuideRetriever(replace(self.config, vector_path=Path("/tmp/absent-kc-guide")), curated=curated)
        self.assertTrue(r.search("What is Waldorf?"))

    def test_query_bounds_and_curated_mode_make_zero_provider_calls(self):
        curated = Mock()
        r = ParentGuideRetriever(self.config, provider=self.provider, curated=curated)
        for question, limit in [("", 3), ("a" * 2001, 3), ("Montessori", 0), (None, 3)]:
            self.assertEqual(r.search(question, limit=limit), [])
            self.assertEqual(r.status.failure_category, "invalid_query")
        self.provider.embed.assert_not_called()
        curated.search.assert_not_called()
        curated.search.return_value = []
        with patch("SystemCode.src.backend.pipeline.parent_guide_retrieval.load_active_index") as loader:
            r = ParentGuideRetriever(replace(self.config, mode=GeneralKnowledgeRetrievalMode.CURATED), curated=curated)
            r.search("What is Montessori?")
        loader.assert_not_called()

    def test_cli_returns_cited_evidence_without_server(self):
        with patch("builtins.print") as output:
            self.assertEqual(main(["What is Montessori?", "--mode", "lexical"]), 0)
        result = json.loads(output.call_args.args[0])
        self.assertEqual(result["status"]["mode"], "lexical")
        self.assertEqual(result["evidence"][0]["citation"]["evidence_scope"], "general")
        self.assertNotIn("question", result)
