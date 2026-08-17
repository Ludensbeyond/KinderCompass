from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from SystemCode.src.scripts.build_knowledge_graph import (
    ADD_CARE_LEVELS,
    ADD_CONCEPTS,
    DELETE_ORPHAN_CONCEPTS,
    SCHEMA_STATEMENTS,
    UPSERT_PRESCHOOL,
    _concept_parameters,
    _parameters,
    build_graph,
    load_catalogue,
)
from SystemCode.src.scripts.prepare_data import (
    DEFAULT_RAW_DIR,
    infer_pedagogy,
    prepare_catalogue,
    write_catalogue,
)


class FakeDriver:
    def __init__(self) -> None:
        self.verified = False
        self.calls: list[tuple[str, dict | None]] = []

    def verify_connectivity(self) -> None:
        self.verified = True

    def run(self, query: str, params: dict | None = None) -> list[dict]:
        self.calls.append((query, params))
        return []


class PrepareDataTests(unittest.TestCase):
    def test_infer_pedagogy_is_conservative(self) -> None:
        self.assertEqual(infer_pedagogy("Sunshine Montessori"), "Montessori")
        self.assertEqual(infer_pedagogy("Example Preschool"), "General")

    def test_current_raw_catalogue_has_required_invariants(self) -> None:
        catalogue = prepare_catalogue(DEFAULT_RAW_DIR)
        self.assertGreater(len(catalogue), 0)
        self.assertTrue(catalogue["school_id"].is_unique)
        self.assertFalse(catalogue["school_id"].isna().any())
        for column in (
            "base_fee", "care_levels", "town", "has_location", "has_fee_data",
            "has_licence_data", "has_vacancy_data",
        ):
            self.assertIn(column, catalogue.columns)

    def test_writer_creates_record_oriented_json(self) -> None:
        catalogue = pd.DataFrame([{"school_id": "CENTRE:A", "name": "A"}])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "catalogue.json"
            written = write_catalogue(catalogue, output)
            self.assertEqual(json.loads(written.read_text(encoding="utf-8")), [
                {"school_id": "CENTRE:A", "name": "A"}
            ])


class BuildGraphTests(unittest.TestCase):
    def school(self) -> dict:
        return {
            "school_id": "CENTRE:A",
            "centre_code": "A",
            "centre_name_x": "Example Preschool",
            "geometry": "POINT Z (103.8123 1.3456 0)",
            "second_languages_offered": "Chinese|Malay",
            "pedagogy": "Montessori",
            "operator_scheme": "Anchor Operator Scheme",
            "spark_certified": "Yes",
            "care_levels": ["Nursery (4 yrs old)"],
            "services_menu": [
                {"levels_offered": "Nursery (4 yrs old)"},
                {"levels_offered": "Kindergarten 1 (5 yrs old)"},
            ],
        }

    def test_default_build_never_clears_graph(self) -> None:
        driver = FakeDriver()
        result = build_graph([self.school()], driver, progress_every=0)
        self.assertTrue(driver.verified)
        self.assertEqual(result, {"schools": 1, "cleared_existing": 0})
        self.assertEqual(
            [query for query, _ in driver.calls[:len(SCHEMA_STATEMENTS)]],
            list(SCHEMA_STATEMENTS),
        )
        school_call = len(SCHEMA_STATEMENTS)
        self.assertEqual(driver.calls[school_call][0], UPSERT_PRESCHOOL)
        self.assertEqual(driver.calls[school_call + 1][0], ADD_CARE_LEVELS)
        self.assertEqual(driver.calls[school_call + 2][0], ADD_CONCEPTS)
        self.assertEqual(driver.calls[-1][0], DELETE_ORPHAN_CONCEPTS)
        self.assertNotIn(("MATCH (n) DETACH DELETE n", None), driver.calls)
        self.assertEqual(
            driver.calls[school_call + 1][1]["levels"],
            ["Kindergarten 1 (5 yrs old)", "Nursery (4 yrs old)"],
        )

    def test_clear_requires_explicit_true(self) -> None:
        driver = FakeDriver()
        result = build_graph([self.school()], driver, clear_existing=True, progress_every=0)
        self.assertEqual(result["cleared_existing"], 1)
        self.assertEqual(driver.calls[0], ("MATCH (n) DETACH DELETE n", None))

    def test_graph_parameters_include_coordinates_and_normalized_concepts(self) -> None:
        school = self.school()
        properties = _parameters(school)
        concepts = _concept_parameters(school)
        self.assertEqual(properties["longitude"], 103.8123)
        self.assertEqual(properties["latitude"], 1.3456)
        self.assertEqual(concepts["languages"], ["Chinese", "Malay"])
        self.assertEqual(concepts["pedagogy"], "Montessori")
        self.assertEqual(concepts["operator_scheme"], "Anchor Operator Scheme")
        self.assertTrue(concepts["spark_certified"])

    def test_catalogue_loader_rejects_duplicate_school_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalogue.json"
            path.write_text(json.dumps([
                {"school_id": "CENTRE:A"}, {"school_id": "CENTRE:A"}
            ]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate school_id"):
                load_catalogue(path)


if __name__ == "__main__":
    unittest.main()
