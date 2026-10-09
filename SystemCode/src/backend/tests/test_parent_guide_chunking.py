"""Reviewed corpus coverage, citation boundaries and qualification retention."""

import copy
import hashlib
import json
import unittest

from SystemCode.src.backend.pipeline.general_knowledge_config import DEFAULT_VECTOR_PATH
from SystemCode.src.backend.pipeline.parent_guide_chunking import (
    ChunkingSettings, chunk_parent_guide, load_parent_guide_chunks, parse_markdown,
)


class ParentGuideChunkingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provenance = json.loads((DEFAULT_VECTOR_PATH / "sources.json").read_text())
        cls.markdown = (DEFAULT_VECTOR_PATH.parent / cls.provenance["document_path"]).read_text()
        cls.chunks = load_parent_guide_chunks()

    def by_mapping(self, mapping_id, chunks=None):
        return [chunk for chunk in (self.chunks if chunks is None else chunks)
                if chunk.mapping_id == mapping_id]

    def test_parser_inventories_sections_tables_and_preserves_lists(self):
        blocks = parse_markdown(self.markdown)
        self.assertEqual(len({block.section_heading for block in blocks if block.section_heading}), 11)
        self.assertEqual(sum(block.kind == "table" for block in blocks), 9)
        checklist = next(block for block in blocks if block.text.startswith("- Child identification"))
        self.assertEqual(checklist.kind, "list")
        self.assertEqual(checklist.subsection_heading, "Step 4 Accept the place and prepare documents")

    def test_every_eligible_mapping_has_reproducible_bounded_chunks(self):
        expected = {m["mapping_id"] for m in self.provenance["approved_mappings"]
                    if m["runtime_eligible"] and m["review_status"] == "verified"}
        self.assertEqual({c.mapping_id for c in self.chunks}, expected)
        self.assertEqual(self.chunks, load_parent_guide_chunks())
        self.assertEqual(len({c.chunk_id for c in self.chunks}), len(self.chunks))
        self.assertEqual([c.matrix_row for c in self.chunks], list(range(len(self.chunks))))
        for chunk in self.chunks:
            self.assertLessEqual(len(chunk.embedding_text), 5000)
            self.assertEqual(chunk.content_sha256, hashlib.sha256(chunk.embedding_text.encode()).hexdigest())
            self.assertIn(chunk.section_heading, chunk.embedding_text)
            json.dumps(chunk.to_dict())

    def test_sentence_and_column_selections_exclude_unreviewed_claims(self):
        self.assertNotIn("Nurturing", self.by_mapping("eydf-framework")[0].text)
        self.assertNotIn("bonuses", self.by_mapping("subsidy-income-ceiling")[0].text)
        self.assertNotIn("cash outlay", self.by_mapping("cda-current-benefits")[0].text)
        self.assertNotIn("reassessment", self.by_mapping("form-1-application")[0].text)
        self.assertNotIn("K2 admission", self.by_mapping("mk-registration-dates")[0].text)
        for mapping_id in ("montessori-emphasis", "ds-ls-role", "eipic-role"):
            text = self.by_mapping(mapping_id)[0].text
            self.assertEqual(len(text.splitlines()), 3)
            self.assertEqual(text.splitlines()[0].count("|"), 3)
            self.assertNotIn("Parent action", text)
            self.assertNotIn("Useful question", text)
        self.assertNotIn("CCTV", "\n".join(c.text for c in self.chunks))

    def test_mixed_fee_table_is_split_by_source_with_conditions(self):
        for mapping_id, forbidden in (("aop-2026-fees", "POP"), ("pop-2026-fees", "AOP"),
                                      ("mk-kcare-2026-fees", "AOP")):
            chunk = self.by_mapping(mapping_id)[0]
            self.assertIn("2026 programme", chunk.text)
            self.assertNotIn("| " + forbidden, chunk.text)
            self.assertEqual(chunk.policy_dates["fee_year"], 2026)
        for mapping_id in ("aop-2026-fees", "pop-2026-fees"):
            self.assertIn("Singapore Citizen", self.by_mapping(mapping_id)[0].text)
        self.assertIn("June and December", self.by_mapping("mk-kcare-2026-fees")[0].text)

    def test_whole_tables_and_forced_row_groups_retain_notes_and_dates(self):
        split = chunk_parent_guide(self.markdown, self.provenance, ChunkingSettings(target_characters=650))
        for mapping_id, year in (("additional-subsidy-2026-table", "2026"),
                                 ("additional-subsidy-2027-table", "2027")):
            self.assertEqual(len(self.by_mapping(mapping_id)), 1)
            groups = self.by_mapping(mapping_id, split)
            self.assertGreater(len(groups), 1)
            rows = []
            for chunk in groups:
                self.assertIn(year, chunk.text.splitlines()[0])
                self.assertIn("co-payment", chunk.text)
                self.assertIn("full-day", chunk.text)
                rows.extend(line for line in chunk.text.splitlines() if line.startswith("| $"))
            self.assertEqual(len(rows), 7)
            self.assertEqual(len(set(rows)), 7)
        self.assertEqual(self.by_mapping("additional-subsidy-2027-table")[0].policy_dates["effective_from"], "2027-01-01")
        self.assertNotIn("effective_until", self.by_mapping("additional-subsidy-2027-table")[0].policy_dates)

    def test_exceptions_and_package_qualifications_stay_atomic(self):
        chunks = chunk_parent_guide(self.markdown, self.provenance, ChunkingSettings(target_characters=250))
        exception = self.by_mapping("basic-subsidy-and-exception", chunks)
        self.assertEqual(len(exception), 1)
        for phrase in ("$6,000", "$1,500", "not a blanket infant-care exemption", "Special Approval"):
            self.assertIn(phrase, exception[0].text)
        package = self.by_mapping("sg-child-support-2027", chunks)
        self.assertEqual(len(package), 1)
        for phrase in ("announced", "1 April 2027", "30 September 2027", "1 October 2027", "PayNow", "CDA"):
            self.assertIn(phrase, package[0].text)

    def test_citations_use_reviewed_fetch_time_and_dates_stay_separate(self):
        sources = {s["source_id"]: s for s in self.provenance["sources"]}
        for chunk in self.chunks:
            source = sources[chunk.primary_source_id]
            self.assertEqual(chunk.citation["url"], source["resolved_url"])
            self.assertEqual(chunk.citation["retrieved_at"], source["source_verified_at"])
            self.assertEqual(chunk.document_checked_on, "2026-10-09")
            self.assertIsNone(chunk.indexed_at)

    def test_source_and_selection_drift_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "source or schema mismatch"):
            chunk_parent_guide(self.markdown + "changed", self.provenance)
        for key in ("content_sha256", "sentence_selection"):
            provenance = copy.deepcopy(self.provenance)
            provenance["approved_mappings"][0][key] = "invalid" if key == "content_sha256" else [99]
            with self.assertRaises(ValueError):
                chunk_parent_guide(self.markdown, provenance)
        provenance = copy.deepcopy(self.provenance)
        provenance["approved_mappings"][5]["context_selections"][0]["content_sha256"] = "invalid"
        with self.assertRaisesRegex(ValueError, "passage hash mismatch"):
            chunk_parent_guide(self.markdown, provenance)

    def test_ids_do_not_depend_on_build_row_or_review_timestamp(self):
        provenance = copy.deepcopy(self.provenance)
        provenance["approved_mappings"].reverse()
        reordered = chunk_parent_guide(self.markdown, provenance)
        self.assertEqual({c.chunk_id for c in reordered}, {c.chunk_id for c in self.chunks})
        provenance["review_completed_on"] = "2026-10-10"
        self.assertEqual(reordered, chunk_parent_guide(self.markdown, provenance))

    def test_ineligible_mappings_and_invalid_citations_are_never_emitted(self):
        provenance = copy.deepcopy(self.provenance)
        provenance["approved_mappings"][0]["runtime_eligible"] = False
        self.assertNotIn("sector-overview", {c.mapping_id for c in chunk_parent_guide(self.markdown, provenance)})
        provenance = copy.deepcopy(self.provenance)
        provenance["sources"][0]["source_verified_at"] = None
        with self.assertRaisesRegex(ValueError, "primary citation"):
            chunk_parent_guide(self.markdown, provenance)

    def test_oversized_qualifications_require_review_instead_of_truncation(self):
        with self.assertRaisesRegex(ValueError, "exceeds passage bound|exceed passage bound"):
            chunk_parent_guide(self.markdown, self.provenance,
                               ChunkingSettings(target_characters=100, max_passage_characters=300))


if __name__ == "__main__":
    unittest.main()
