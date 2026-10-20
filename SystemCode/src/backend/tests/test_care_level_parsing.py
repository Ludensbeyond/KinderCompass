import unittest

from stage1.care_level_parsing import (
    care_level_supported_by_message,
    explicit_care_level_from_message,
)


class CareLevelParsingTests(unittest.TestCase):
    def test_extracts_all_supported_levels(self):
        cases = {
            "infant care near home": "Infant (2 to 18 mths)",
            "playgroup with chinese": "Playgroup (18 mths to 2 yrs old)",
            "pre-nursery class": "Pre-Nursery (3 yrs old)",
            "pre nursery option": "Pre-Nursery (3 yrs old)",
            "nursery school spark": "Nursery (4 yrs old)",
            "spark certified k1 school": "Kindergarten 1 (5 yrs old)",
            "looking for k2": "Kindergarten 2 (6 yrs old)",
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                self.assertEqual(explicit_care_level_from_message(message), expected)

    def test_kindergarten_radius_does_not_set_k1(self):
        self.assertIsNone(
            explicit_care_level_from_message("kindergarten 1km from my home, bilingual")
        )
        self.assertFalse(care_level_supported_by_message(
            "kindergarten 1km from my home, bilingual",
            "Kindergarten 1 (5 yrs old)",
        ))

    def test_nursery_phrase_is_supported_on_follow_up_message(self):
        self.assertTrue(care_level_supported_by_message(
            "nursery with spark",
            "Nursery (4 yrs old)",
        ))


if __name__ == "__main__":
    unittest.main()
