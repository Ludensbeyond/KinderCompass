"""Tool lifecycle logs remain useful without exposing tool data."""

import logging
import unittest
from unittest.mock import patch

from SystemCode.src.backend.agents.observability import observe_tool_execution


class ToolExecutionLoggingTests(unittest.TestCase):
    def test_started_is_emitted_before_execution_and_completion_matches(self):
        with self.assertLogs("kindercompass.conversation_agent", level=logging.INFO) as logs:
            with observe_tool_execution("search_general_knowledge"):
                self.assertEqual(len(logs.output), 1)
                self.assertIn("event=started", logs.output[0])
            self.assertEqual(len(logs.output), 2)
        self.assertIn("event=completed", logs.output[1])
        ids = [line.split("execution_id=")[1].split()[0] for line in logs.output]
        self.assertEqual(ids[0], ids[1])
        self.assertIn("tool=search_general_knowledge", logs.output[0])
        self.assertIn("elapsed_ms=", logs.output[1])

    def test_failure_preserves_exception_without_logging_its_contents(self):
        error = TimeoutError("private provider credential and family information")
        with self.assertLogs("kindercompass.conversation_agent", level=logging.INFO) as logs:
            with self.assertRaises(TimeoutError) as caught:
                with observe_tool_execution("search_general_knowledge"):
                    raise error
        self.assertIs(caught.exception, error)
        self.assertEqual(len(logs.output), 2)
        self.assertIn("event=failed", logs.output[1])
        self.assertNotIn(str(error), "\n".join(logs.output))

    def test_logging_failure_does_not_interrupt_execution(self):
        with patch("SystemCode.src.backend.agents.observability.LOGGER.info", side_effect=RuntimeError):
            with observe_tool_execution("search_general_knowledge"):
                pass
            with self.assertRaises(ValueError):
                with observe_tool_execution("search_general_knowledge"):
                    raise ValueError("original error")
