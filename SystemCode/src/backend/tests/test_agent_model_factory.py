import unittest
from unittest.mock import Mock

from SystemCode.src.backend.agents.model_factory import (
    ModelFactoryError,
    ModelFactoryErrorCode,
    create_agent_model,
)


class AgentModelFactoryTests(unittest.TestCase):
    def test_deterministic_mode_does_not_construct_a_client_or_require_credentials(self):
        client_factory = Mock()

        model = create_agent_model({}, client_factory=client_factory)

        self.assertIsNone(model)
        client_factory.assert_not_called()

    def test_agent_mode_constructs_client_lazily_with_backend_configuration(self):
        expected_client = object()
        client_factory = Mock(return_value=expected_client)
        environ = {
            "WEB_RAG_ANSWER_MODE": "agent",
            "OPENAI_API_KEY": "test-api-key",
            "OPENAI_WEB_RAG_MODEL": "gpt-test-model",
            "OPENAI_WEB_RAG_TIMEOUT_SECONDS": "12.5",
        }

        model = create_agent_model(environ, client_factory=client_factory)

        self.assertIs(model, expected_client)
        client_factory.assert_called_once_with(
            model="gpt-test-model",
            timeout=12.5,
            api_key="test-api-key",
        )

    def test_agent_mode_uses_bounded_configuration_defaults(self):
        client_factory = Mock(return_value=object())

        create_agent_model(
            {"WEB_RAG_ANSWER_MODE": "agent", "OPENAI_API_KEY": "test-api-key"},
            client_factory=client_factory,
        )

        self.assertEqual(client_factory.call_args.kwargs["model"], "gpt-4o-mini")
        self.assertEqual(client_factory.call_args.kwargs["timeout"], 8.0)

    def test_missing_credentials_and_invalid_timeouts_are_typed_errors(self):
        cases = (
            (
                {"WEB_RAG_ANSWER_MODE": "agent"},
                ModelFactoryErrorCode.MISSING_CREDENTIALS,
            ),
            (
                {
                    "WEB_RAG_ANSWER_MODE": "agent",
                    "OPENAI_API_KEY": "test-api-key",
                    "OPENAI_WEB_RAG_TIMEOUT_SECONDS": "0",
                },
                ModelFactoryErrorCode.INVALID_CONFIGURATION,
            ),
            (
                {
                    "WEB_RAG_ANSWER_MODE": "agent",
                    "OPENAI_API_KEY": "test-api-key",
                    "OPENAI_WEB_RAG_TIMEOUT_SECONDS": "31",
                },
                ModelFactoryErrorCode.INVALID_CONFIGURATION,
            ),
        )
        for environ, expected_code in cases:
            with self.subTest(expected_code=expected_code), self.assertRaises(ModelFactoryError) as raised:
                create_agent_model(environ, client_factory=Mock())
            self.assertEqual(raised.exception.code, expected_code)

    def test_initialization_error_does_not_expose_secret_or_provider_details(self):
        secret = "sk-secret-that-must-not-escape"

        def failing_factory(**kwargs):
            raise RuntimeError(f"provider rejected {kwargs['api_key']}")

        with self.assertRaises(ModelFactoryError) as raised:
            create_agent_model(
                {"WEB_RAG_ANSWER_MODE": "agent", "OPENAI_API_KEY": secret},
                client_factory=failing_factory,
            )

        error = raised.exception
        self.assertEqual(error.code, ModelFactoryErrorCode.INITIALIZATION_FAILED)
        self.assertNotIn(secret, str(error))
        self.assertNotIn("provider rejected", str(error))
        self.assertIsNone(error.__cause__)


if __name__ == "__main__":
    unittest.main()
