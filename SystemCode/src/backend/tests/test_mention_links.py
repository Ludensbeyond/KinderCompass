import unittest

from stage1.mention_links import mention_search_query, parent_mention_links
from stage1.query_builder import build_stage1_query


class MentionLinkTests(unittest.TestCase):
    def test_query_includes_name_postal_code_and_singapore(self):
        self.assertEqual(
            mention_search_query("PCF Sparkletots", 540231),
            "PCF Sparkletots 540231 Singapore",
        )

    def test_missing_postal_code_still_searches_by_name(self):
        self.assertEqual(mention_search_query("Example Preschool"), "Example Preschool Singapore")

    def test_incomplete_postal_code_is_omitted(self):
        self.assertEqual(mention_search_query("Example Preschool", 12345), "Example Preschool Singapore")

    def test_links_are_encoded_searches_not_place_ids(self):
        links = parent_mention_links("Bright Kids", "123456")
        self.assertEqual(links["query"], "Bright Kids 123456 Singapore")
        self.assertIn("google.com/maps/search", links["google_maps"])
        self.assertIn("query=Bright+Kids+123456+Singapore", links["google_maps"])
        self.assertIn("google.com/search", links["google_search"])
        self.assertIn("reviews", links["google_search"])
        self.assertIn("reddit.com/search", links["reddit"])
        self.assertNotIn("place_id", links["google_maps"])


class Stage1PostalCodeReturnTests(unittest.TestCase):
    def test_stage1_query_returns_school_postal_code(self):
        query, _params = build_stage1_query()
        self.assertIn("p.postal_code AS postal_code", query)


if __name__ == "__main__":
    unittest.main()
