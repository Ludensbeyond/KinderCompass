import importlib
import unittest

from SystemCode.src.backend.agents.config import (
    ConversationAgentMode,
    WebRagAnswerMode,
    get_conversation_agent_mode,
    get_web_rag_answer_mode,
)


class AgentDependencyTests(unittest.TestCase):
    def test_langgraph_and_langchain_openai_import(self):
        graph = importlib.import_module("langgraph.graph")
        provider = importlib.import_module("langchain_openai")

        self.assertTrue(hasattr(graph, "StateGraph"))
        self.assertTrue(hasattr(provider, "ChatOpenAI"))


class WebRagAnswerModeTests(unittest.TestCase):
    def test_missing_mode_defaults_to_deterministic(self):
        self.assertEqual(
            get_web_rag_answer_mode({}),
            WebRagAnswerMode.DETERMINISTIC,
        )

    def test_supported_modes_are_parsed(self):
        self.assertEqual(
            get_web_rag_answer_mode({"WEB_RAG_ANSWER_MODE": " deterministic "}),
            WebRagAnswerMode.DETERMINISTIC,
        )
        self.assertEqual(
            get_web_rag_answer_mode({"WEB_RAG_ANSWER_MODE": "AGENT"}),
            WebRagAnswerMode.AGENT,
        )

    def test_invalid_mode_falls_back_to_deterministic(self):
        self.assertEqual(
            get_web_rag_answer_mode({"WEB_RAG_ANSWER_MODE": "experimental"}),
            WebRagAnswerMode.DETERMINISTIC,
        )


class ConversationAgentModeTests(unittest.TestCase):
    def test_missing_empty_and_invalid_modes_fail_closed(self):
        for environ in ({}, {"CONVERSATION_AGENT_MODE": ""}, {"CONVERSATION_AGENT_MODE": "other"}):
            with self.subTest(environ=environ):
                self.assertEqual(
                    get_conversation_agent_mode(environ),
                    ConversationAgentMode.DETERMINISTIC,
                )

    def test_all_supported_modes_are_parsed_case_insensitively(self):
        for value, expected in (
            (" deterministic ", ConversationAgentMode.DETERMINISTIC),
            ("SHADOW", ConversationAgentMode.SHADOW),
            ("agent", ConversationAgentMode.AGENT),
        ):
            with self.subTest(value=value):
                self.assertEqual(
                    get_conversation_agent_mode({"CONVERSATION_AGENT_MODE": value}), expected,
                )

if __name__ == "__main__":
    unittest.main()
