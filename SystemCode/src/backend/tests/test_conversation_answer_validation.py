import unittest

from agents.conversation_response import _contradictory_yes_no_lead, _name_appears_in_span


class ConversationAnswerValidationTests(unittest.TestCase):
    def test_contradictory_yes_no_lead_detects_misleading_transport_answer(self):
        bad = (
            "Yes—E-BRIDGE PRE-SCHOOL PTE LTD does not provide transport. "
            "MY FIRST SKOOL does not provide transport."
        )
        self.assertTrue(_contradictory_yes_no_lead(bad))

    def test_contradictory_yes_no_lead_allows_direct_negative_answer(self):
        good = "Neither selected preschool provides transport."
        self.assertFalse(_contradictory_yes_no_lead(good))

    def test_contradictory_yes_no_lead_detects_yes_before_not_malay(self):
        bad = "Yes. MY FIRST SKOOL offers Chinese as a second language, not Malay."
        self.assertTrue(_contradictory_yes_no_lead(bad))

    def test_contradictory_yes_no_lead_allows_yes_when_malay_offered(self):
        good = "Yes. MY FIRST SKOOL offers Malay as a second language."
        self.assertFalse(_contradictory_yes_no_lead(good))

    def test_name_appears_in_span_accepts_catalogue_prefix_in_list_bullet(self):
        catalogue = "AGAPE LITTLE UNI @ COMMONWEALTH"
        bullet = "AGAPE LITTLE UNI COMMONWEALTH, 401,Commonwealth Drive"
        self.assertTrue(_name_appears_in_span(catalogue, bullet))


if __name__ == "__main__":
    unittest.main()
