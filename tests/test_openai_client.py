from __future__ import annotations

import unittest
from urllib.request import Request

from coding_agent.llm.openai_client import (
    OpenAIConfigurationError,
    OpenAIHttpClient,
    OpenAIRequestError,
    OpenAIResponseError,
)
from coding_agent.llm.openai_provider import OpenAIResponsesProvider
from coding_agent.llm.openai_transport import _RejectRedirectHandler
from coding_agent.llm.provider import LLMMessage

from tests.openai_provider_test_support import QueueTransport, response
from tests.support import WorkspaceTestCase


class OpenAIClientTests(WorkspaceTestCase):
    def test_transport_rejects_redirects(self) -> None:
        handler = _RejectRedirectHandler()
        request = Request("https://api.openai.com/v1/responses")
        redirected = handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://example.test/redirect",
        )
        self.assertIsNone(redirected)

    def test_client_requires_safe_configuration(self) -> None:
        with self.assertRaisesRegex(OpenAIConfigurationError, "OPENAI_API_KEY"):
            OpenAIHttpClient.from_env({})
        with self.assertRaisesRegex(OpenAIConfigurationError, "HTTPS"):
            OpenAIHttpClient("test-key", base_url="http://api.openai.test/v1")

    def test_client_retries_transient_status_with_bound(self) -> None:
        transport = QueueTransport(
            [
                response(429, {"error": {"message": "try later"}}, **{"retry-after": "0"}),
                response(200, {"ok": True}),
            ]
        )
        delays: list[float] = []
        client = OpenAIHttpClient(
            "test-key",
            maximum_retries=1,
            transport=transport,
            sleep=delays.append,
        )
        self.assertEqual(client.post_json("/responses", {"input": "test"}), {"ok": True})
        self.assertEqual(len(transport.calls), 2)
        self.assertEqual(delays, [0.0])

    def test_client_retries_timeout_with_bound(self) -> None:
        transport = QueueTransport([TimeoutError("timed out"), response(200, {"ok": True})])
        delays: list[float] = []
        client = OpenAIHttpClient(
            "test-key",
            maximum_retries=1,
            transport=transport,
            sleep=delays.append,
        )
        self.assertEqual(client.post_json("/responses", {"input": "test"}), {"ok": True})
        self.assertEqual(delays, [1.0])

    def test_client_redacts_key_from_terminal_error(self) -> None:
        transport = QueueTransport(
            [response(401, {"error": {"message": "invalid test-sensitive-key"}})]
        )
        client = OpenAIHttpClient(
            "test-sensitive-key",
            maximum_retries=0,
            transport=transport,
        )
        with self.assertRaises(OpenAIRequestError) as raised:
            client.post_json("/responses", {"input": "test"})
        self.assertNotIn("test-sensitive-key", str(raised.exception))
        self.assertEqual(raised.exception.status_code, 401)
        self.assertFalse(raised.exception.retryable)

    def test_client_rejects_non_standard_json_numbers(self) -> None:
        transport = QueueTransport([response(200, {"value": float("nan")})])
        client = OpenAIHttpClient("test-key", transport=transport)
        with self.assertRaisesRegex(OpenAIResponseError, "valid UTF-8 JSON"):
            client.post_json("/responses", {"input": "test"})

    def test_responses_provider_maps_text_usage_and_request(self) -> None:
        transport = QueueTransport(
            [
                response(
                    200,
                    {
                        "id": "resp_fixture",
                        "model": "gpt-5.6",
                        "status": "completed",
                        "usage": {"input_tokens": 10, "output_tokens": 4, "ignored": "x"},
                        "output": [
                            {
                                "type": "message",
                                "content": [{"type": "output_text", "text": '{"ok":true}'}],
                            }
                        ],
                    },
                )
            ]
        )
        provider = OpenAIResponsesProvider(
            OpenAIHttpClient("test-key", transport=transport),
            maximum_output_tokens=1_000,
        )
        result = provider.complete([LLMMessage("user", "Return JSON")])
        self.assertEqual(result.content, '{"ok":true}')
        self.assertEqual(result.usage.input_tokens, 10)
        self.assertEqual(result.usage.output_tokens, 4)
        self.assertEqual(result.usage.input_tokens_known_calls, 1)
        self.assertEqual(result.usage.total_tokens_known_calls, 0)
        request_payload = transport.calls[0]["payload"]
        assert isinstance(request_payload, dict)
        self.assertEqual(request_payload["model"], "gpt-5.6")
        self.assertFalse(request_payload["store"])

    def test_responses_provider_rejects_missing_output_text(self) -> None:
        transport = QueueTransport(
            [response(200, {"model": "gpt-5.6", "status": "completed", "output": []})]
        )
        provider = OpenAIResponsesProvider(OpenAIHttpClient("test-key", transport=transport))
        with self.assertRaisesRegex(OpenAIResponseError, "output text"):
            provider.complete([LLMMessage("user", "Return JSON")])


if __name__ == "__main__":
    unittest.main()
