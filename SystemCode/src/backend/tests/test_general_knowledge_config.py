"""Opt-in execution bounds and reviewed parent-guide provenance gates."""

import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

from SystemCode.src.backend.pipeline.general_knowledge_config import (
    DEFAULT_VECTOR_PATH,
    GeneralKnowledgeRetrievalMode,
    REPOSITORY_ROOT,
    get_general_knowledge_config,
)


class GeneralKnowledgeConfigurationTests(unittest.TestCase):
    def test_unrecognised_modes_never_opt_into_vectors(self):
        for mode in (None, "", "  ", "invalid"):
            environ = {} if mode is None else {"GENERAL_KNOWLEDGE_RETRIEVAL_MODE": mode}
            with self.subTest(mode=mode):
                config = get_general_knowledge_config(environ)
                self.assertEqual(config.mode, GeneralKnowledgeRetrievalMode.CURATED)
                self.assertEqual(config.vector_path, DEFAULT_VECTOR_PATH)
                self.assertEqual(config.embedding_model, "text-embedding-3-small")
                self.assertEqual(config.embedding_dimensions, 1536)

    def test_explicit_opt_in_is_independent_of_working_directory(self):
        with tempfile.TemporaryDirectory() as directory, patch("os.getcwd", return_value=directory):
            config = get_general_knowledge_config({
                "GENERAL_KNOWLEDGE_RETRIEVAL_MODE": " VECTOR ",
                "GENERAL_KNOWLEDGE_VECTOR_PATH": "SystemCode/data/vectors/parent_guide",
            })
        self.assertEqual(config.mode, GeneralKnowledgeRetrievalMode.VECTOR)
        self.assertEqual(config.vector_path, DEFAULT_VECTOR_PATH)

    def test_execution_bounds_and_model_mismatch_are_rejected_without_values(self):
        for key, values in {
            "GENERAL_KNOWLEDGE_TIMEOUT_SECONDS": ["0", "31", "nan", "inf", "secret-value"],
            "GENERAL_KNOWLEDGE_MAX_QUERY_CHARACTERS": ["0", "2001", "3.5"],
            "GENERAL_KNOWLEDGE_EMBEDDING_PROVIDER": ["azure", ""],
            "GENERAL_KNOWLEDGE_EMBEDDING_MODEL": ["gpt-4o-mini", ""],
            "GENERAL_KNOWLEDGE_EMBEDDING_DIMENSIONS": ["3072", "0"],
        }.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    with self.assertRaisesRegex(ValueError, "^Invalid general knowledge configuration.$"):
                        get_general_knowledge_config({key: value})


class ParentGuideProvenanceTests(unittest.TestCase):
    def test_inventory_and_approved_passages_match_maintained_source(self):
        folder = REPOSITORY_ROOT / "SystemCode/data/vectors"
        mapping = json.loads((folder / "parent_guide/sources.json").read_text())
        raw = (folder / mapping["document_path"]).read_bytes()
        self.assertEqual(mapping["document_sha256"], hashlib.sha256(raw).hexdigest())
        lines = raw.decode().splitlines()
        self.assertEqual(len(mapping["sections"]), 11)
        self.assertEqual(sum(len(section["tables"]) for section in mapping["sections"]), 9)
        sources = {source["source_id"]: source for source in mapping["sources"]}
        self.assertEqual(len(sources), len(mapping["sources"]))
        for section in mapping["sections"]:
            self.assertTrue(section["exclusions_and_review_notes"])
            self.assertTrue(set(section["source_ids"]) <= sources.keys())
        for passage in mapping["approved_mappings"]:
            source = sources[passage["primary_source_id"]]
            self.assertEqual(source["http_status"], 200)
            self.assertEqual(source["fetch_status"], "content_available")
            self.assertTrue(source["resolved_url"].startswith("https://"))
            self.assertEqual(passage["source_verified_at"], source["source_verified_at"])
            self.assertTrue(passage["runtime_eligible"])
            text = "\n\n".join("\n".join(lines[start-1:end]) for start, end in passage["line_ranges"])
            self.assertEqual(passage["content_sha256"], hashlib.sha256(text.encode()).hexdigest())
        self.assertIsNone(mapping["indexed_at"])


if __name__ == "__main__":
    unittest.main()
