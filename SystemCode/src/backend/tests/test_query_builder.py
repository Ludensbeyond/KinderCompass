import unittest

from stage1.evidence import evidence_details
from stage1.nlp_mapper import map_text_to_filters
from stage1.query_builder import build_stage1_query
from stage1.scorer import score_school


class Stage1QueryBuilderTests(unittest.TestCase):
    def test_unfiltered_query_returns_properties_and_empty_path(self):
        query, params = build_stage1_query()
        self.assertIn("MATCH (p:Preschool)", query)
        self.assertNotIn("[:TEACHES_IN]", query)
        self.assertNotIn("[:USES_PEDAGOGY]", query)
        self.assertNotIn("[:HAS_CERTIFICATION]", query)
        self.assertIn("[] AS retrieval_path", query)
        self.assertIn("p.postal_code AS postal_code", query)
        self.assertEqual(params, {})

    def test_required_language_uses_teaches_in_not_property_contains(self):
        query, params = build_stage1_query({"hard_constraints": {"language": "Chinese"}})
        self.assertIn("MATCH (p)-[:TEACHES_IN]->(lang:Language)", query)
        self.assertIn("toLower(toString(lang.name)) = toLower($language)", query)
        self.assertNotIn("second_languages_offered", query.split("RETURN", 1)[0])
        self.assertIn("{rel: 'TEACHES_IN'", query)
        self.assertEqual(params["language"], "Chinese")

    def test_required_level_uses_serves_level(self):
        query, params = build_stage1_query({
            "hard_constraints": {"level": "Nursery (4 yrs old)"},
        })
        self.assertIn("MATCH (p)-[:SERVES_LEVEL]->(c:CareLevel)", query)
        self.assertIn("c.name = $level", query)
        self.assertIn("{rel: 'SERVES_LEVEL'", query)
        self.assertEqual(params["level"], "Nursery (4 yrs old)")

    def test_town_name_uses_located_in(self):
        query, params = build_stage1_query({"town": "Sengkang"})
        self.assertIn("MATCH (p)-[:LOCATED_IN]->(t:Town)", query)
        self.assertIn("toLower(toString(t.name)) = toLower($town)", query)
        self.assertIn("{rel: 'LOCATED_IN'", query)
        self.assertEqual(params["town"], "Sengkang")

    def test_postal_code_stays_a_property_filter(self):
        query, params = build_stage1_query({"town": "540231"})
        self.assertIn("p.postal_code = $postal_code", query)
        self.assertNotIn("[:LOCATED_IN]", query)
        self.assertIn("{rel: 'POSTAL_CODE'", query)
        self.assertEqual(params["postal_code"], 540231)

    def test_hybrid_query_combines_graph_and_structured_filters(self):
        query, params = build_stage1_query({
            "town": "Woodlands",
            "hard_constraints": {
                "level": "Nursery (4 yrs old)",
                "language": "Chinese",
            },
        })
        self.assertIn("[:LOCATED_IN]", query)
        self.assertIn("[:SERVES_LEVEL]", query)
        self.assertIn("[:TEACHES_IN]", query)
        self.assertNotIn("[:HAS_CERTIFICATION]", query)
        self.assertNotIn("[:USES_PEDAGOGY]", query)
        self.assertEqual(params, {
            "town": "Woodlands",
            "level": "Nursery (4 yrs old)",
            "language": "Chinese",
        })

    def test_spark_preference_does_not_filter_in_cypher(self):
        query, params = build_stage1_query(map_text_to_filters("SPARK"))
        self.assertNotIn("[:HAS_CERTIFICATION]", query)
        self.assertNotIn("[:USES_PEDAGOGY]", query)
        self.assertIn("p.last_updated AS last_updated", query)
        self.assertIn("[] AS retrieval_path", query)
        self.assertEqual(params, {})

    def test_preferred_pedagogy_does_not_filter_in_cypher(self):
        query, _params = build_stage1_query(map_text_to_filters("Montessori"))
        self.assertNotIn("[:USES_PEDAGOGY]", query)
        self.assertNotIn("p.pedagogy", query.split("RETURN", 1)[0])

    def test_required_language_from_text_uses_relationship(self):
        query, params = build_stage1_query(map_text_to_filters("must have Chinese"))
        self.assertIn("[:TEACHES_IN]", query)
        self.assertEqual(params["language"], "Chinese")

    def test_legacy_pedagogy_key_uses_relationship(self):
        query, params = build_stage1_query({"pedagogy": "Play-based"})
        self.assertIn("[:USES_PEDAGOGY]", query)
        self.assertEqual(params["pedagogy"], "Play-based")


class GraphRetrievalEvidenceTests(unittest.TestCase):
    def test_language_breakdown_keeps_field_provenance_and_adds_path(self):
        school = {
            "second_languages_offered": "Chinese",
            "last_updated": "2026-01-01",
            "retrieval_path": [
                {"rel": "TEACHES_IN", "label": "Language", "name": "Chinese"},
            ],
        }
        details = evidence_details("language:Chinese", school, True, True)
        self.assertEqual(details["source_method"], "structured_record")
        self.assertEqual(details["retrieval_method"], "graph_traversal")
        self.assertEqual(details["retrieval_path"][0]["rel"], "TEACHES_IN")
        self.assertEqual(details["source"], "ECDA/LifeSG preschool dataset")

    def test_pedagogy_stays_derived_when_path_has_no_pedagogy_edge(self):
        school = {
            "pedagogy": "Montessori",
            "last_updated": "2026-01-01",
            "retrieval_path": [
                {"rel": "TEACHES_IN", "label": "Language", "name": "Chinese"},
            ],
        }
        profile = map_text_to_filters("Montessori")
        scored = score_school(profile, school)
        evidence = scored["match_breakdown"][0]
        self.assertEqual(evidence["source_method"], "derived_from_centre_name")
        self.assertNotIn("retrieval_method", evidence)
        self.assertEqual(scored["retrieval_path"][0]["rel"], "TEACHES_IN")


if __name__ == "__main__":
    unittest.main()
