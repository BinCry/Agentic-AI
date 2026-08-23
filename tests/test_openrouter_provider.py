from __future__ import annotations

import unittest

from coding_agent.llm.openai_client import OpenAIRequestError, OpenAIResponseError
from coding_agent.llm.openrouter_provider import (
    OpenRouterConfigurationError,
    OpenRouterResponsesProvider,
)
from coding_agent.llm.provider import LLMMessage

from tests.openai_provider_test_support import QueueTransport, response
from tests.support import WorkspaceTestCase


class OpenRouterProviderTests(WorkspaceTestCase):
    def test_environment_requires_key_and_valid_bounds(self) -> None:
        with self.assertRaisesRegex(OpenRouterConfigurationError, "OPENROUTER_API_KEY"):
            OpenRouterResponsesProvider.from_env({})
        with self.assertRaisesRegex(OpenRouterConfigurationError, "must be an integer"):
            OpenRouterResponsesProvider.from_env(
                {
                    "OPENROUTER_API_KEY": "test-key",
                    "OPENROUTER_MAX_OUTPUT_TOKENS": "invalid",
                }
            )

    def test_maps_responses_request_response_and_usage(self) -> None:
        transport = QueueTransport(
            [
                response(
                    200,
                    {
                        "id": "resp_fixture",
                        "model": "stealth/ox-alpha",
                        "status": "completed",
                        "usage": {
                            "input_tokens": 9,
                            "output_tokens": 4,
                            "total_tokens": 13,
                            "output_tokens_details": {"reasoning_tokens": 2},
                            "ignored": "value",
                        },
                        "reasoning_details": [{"private": "must-not-survive"}],
                        "output": [
                            {
                                "type": "message",
                                "content": [
                                    {"type": "output_text", "text": '{"ok":true}'}
                                ],
                            }
                        ],
                    },
                )
            ]
        )
        provider = OpenRouterResponsesProvider.from_env(
            {
                "OPENROUTER_API_KEY": "test-key",
                "OPENROUTER_REASONING_EFFORT": "high",
                "OPENROUTER_MAX_OUTPUT_TOKENS": "1000",
            },
            transport=transport,
        )

        result = provider.complete([LLMMessage("user", "Return JSON")])

        self.assertEqual(provider.provider_name, "openrouter-responses")
        self.assertEqual(result.content, '{"ok":true}')
        self.assertEqual(result.model, "stealth/ox-alpha")
        self.assertEqual(result.usage.total_tokens, 13)
        self.assertEqual(result.usage.reasoning_tokens, 2)
        self.assertEqual(result.usage.known_calls, 1)
        self.assertNotIn("reasoning_details", result.provider_metadata)
        call = transport.calls[0]
        self.assertEqual(call["url"], "https://openrouter.ai/api/v1/responses")
        payload = call["payload"]
        assert isinstance(payload, dict)
        self.assertEqual(payload["model"], "stealth/ox-alpha")
        self.assertEqual(payload["reasoning"], {"effort": "high"})
        self.assertEqual(payload["max_output_tokens"], 1000)
        self.assertFalse(payload["store"])

    def test_redacts_key_from_request_failure(self) -> None:
        transport = QueueTransport(
            [response(401, {"error": {"message": "invalid test-sensitive-key"}})]
        )
        provider = OpenRouterResponsesProvider.from_env(
            {
                "OPENROUTER_API_KEY": "test-sensitive-key",
                "OPENROUTER_MAX_RETRIES": "0",
            },
            transport=transport,
        )
        with self.assertRaises(OpenAIRequestError) as raised:
            provider.complete([LLMMessage("user", "Return JSON")])
        self.assertNotIn("test-sensitive-key", str(raised.exception))
        self.assertEqual(raised.exception.status_code, 401)

    def test_rejects_missing_output_text(self) -> None:
        transport = QueueTransport(
            [response(200, {"model": "stealth/ox-alpha", "output": []})]
        )
        provider = OpenRouterResponsesProvider.from_env(
            {"OPENROUTER_API_KEY": "test-key"}, transport=transport
        )
        with self.assertRaisesRegex(OpenAIResponseError, "output text"):
            provider.complete([LLMMessage("user", "Return JSON")])


if __name__ == "__main__":
    unittest.main()
