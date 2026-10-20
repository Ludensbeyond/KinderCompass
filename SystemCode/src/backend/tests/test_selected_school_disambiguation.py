import unittest

from agents.contracts import ConversationExchange, InitialConversationContext, SchoolIdentityContext
from agents.conversation_loop import (
    _facts_operation_for_question,
    _selected_school_disambiguation_hint,
    _selected_schools_list_question_hint,
    _selected_schools_pronoun_hint,
)
from services.conversation_context_service import CAPABILITIES


class SelectedSchoolDisambiguationTests(unittest.TestCase):
    def test_both_reply_steers_to_programmes_for_language_question(self):
        context = InitialConversationContext(
            message="Both",
            selected_schools=[
                SchoolIdentityContext(school_id="CENTRE:A", name="School A"),
                SchoolIdentityContext(school_id="CENTRE:B", name="School B"),
            ],
            recent_exchanges=[ConversationExchange(
                user="what language does the selected school provides?",
                assistant="Which selected school do you mean: School A or School B?",
            )],
            catalogue_version="synthetic",
            capabilities=list(CAPABILITIES),
        )
        hint = _selected_school_disambiguation_hint(context)
        self.assertIn("read_school_facts", hint)
        self.assertIn("programmes", hint)
        self.assertIn("CENTRE:A", hint)
        self.assertIn("CENTRE:B", hint)
        self.assertIn("search_rank_compare_schools", hint)

    def test_both_reply_ignored_without_disambiguation_question(self):
        context = InitialConversationContext(
            message="Both",
            selected_schools=[
                SchoolIdentityContext(school_id="CENTRE:A", name="School A"),
                SchoolIdentityContext(school_id="CENTRE:B", name="School B"),
            ],
            recent_exchanges=[ConversationExchange(
                user="Compare fees",
                assistant="School A is cheaper than School B.",
            )],
            catalogue_version="synthetic",
            capabilities=list(CAPABILITIES),
        )
        self.assertEqual(_selected_school_disambiguation_hint(context), "")

    def test_halal_they_question_targets_food_for_all_selected(self):
        context = InitialConversationContext(
            message="Do they provide Halal meals?",
            selected_schools=[
                SchoolIdentityContext(school_id="CENTRE:A", name="School A"),
                SchoolIdentityContext(school_id="CENTRE:B", name="School B"),
            ],
            catalogue_version="synthetic",
            capabilities=list(CAPABILITIES),
        )
        hint = _selected_schools_pronoun_hint(context)
        self.assertIn("read_school_facts", hint)
        self.assertIn("food", hint)
        self.assertIn("CENTRE:A", hint)
        self.assertIn("CENTRE:B", hint)
        self.assertIn("Do not ask which school", hint)

    def test_both_after_halal_clarification_uses_food_operation(self):
        context = InitialConversationContext(
            message="Both",
            selected_schools=[
                SchoolIdentityContext(school_id="CENTRE:A", name="E-BRIDGE PRE-SCHOOL"),
                SchoolIdentityContext(school_id="CENTRE:B", name="MY FIRST SKOOL"),
            ],
            recent_exchanges=[ConversationExchange(
                user="Do they provide Halal meals?",
                assistant="I need to know which school you mean. Do you want me to check E-BRIDGE or both?",
            )],
            catalogue_version="synthetic",
            capabilities=list(CAPABILITIES),
        )
        self.assertEqual(_facts_operation_for_question("Do they provide Halal meals?"), "food")
        hint = _selected_school_disambiguation_hint(context)
        self.assertIn("operation food", hint)
        self.assertIn("CENTRE:A", hint)

    def test_any_school_in_list_has_malay_triggers_list_hint(self):
        context = InitialConversationContext(
            message="Are there any school in the list that has Malay language?",
            selected_schools=[SchoolIdentityContext(school_id="CENTRE:A", name="MY FIRST SKOOL")],
            catalogue_version="synthetic",
            capabilities=list(CAPABILITIES),
        )
        hint = _selected_schools_list_question_hint(context)
        self.assertIn("read_school_facts", hint)
        self.assertIn("answer Yes only if", hint)

    def test_malay_in_list_question_steers_to_read_school_facts(self):
        context = InitialConversationContext(
            message="Are there any schools in the list that offer Malay language?",
            selected_schools=[
                SchoolIdentityContext(school_id="CENTRE:A", name="School A"),
                SchoolIdentityContext(school_id="CENTRE:B", name="School B"),
            ],
            catalogue_version="synthetic",
            capabilities=list(CAPABILITIES),
        )
        hint = _selected_schools_list_question_hint(context)
        self.assertIn("read_school_facts", hint)
        self.assertIn("programmes", hint)
        self.assertIn("CENTRE:A", hint)
        self.assertNotIn("search_rank_compare_schools", hint.split("Do not call")[0])


if __name__ == "__main__":
    unittest.main()
