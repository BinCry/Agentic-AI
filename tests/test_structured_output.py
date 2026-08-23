from __future__ import annotations

import unittest
from collections.abc import Sequence

from coding_agent.llm.provider import LLMMessage, LLMResponse, ModelUsage
from coding_agent.llm.structured_output import StructuredOutputError, StructuredOutputService
from coding_agent.models.decisions import IssueAnalysis


VALID_ANALYSIS = (
    '{"task_type":"bug_fix","problem":"Broken",'
    '"expected_behavior":"Works","acceptance_criteria":["Passes"],'
    '"search_queries":[],"risks":[]}'
)


class FakeProvider:
    provider_name = "fake"

    def __init__(self, responses: list[str | LLMResponse]) -> None:
        self.responses = responses
        self.calls: list[list[LLMMessage]] = []

    def complete(self, messages: Sequence[LLMMessage]) -> LLMResponse:
        self.calls.append(list(messages))
        response = self.responses.pop(0)
        return (
            response
            if isinstance(response, LLMResponse)
            else LLMResponse(content=response, model="fake-model")
        )


class StructuredOutputTests(unittest.TestCase):
    def test_model_usage_rejects_unqualified_or_invalid_counts(self) -> None:
        with self.assertRaisesRegex(ValueError, "known call"):
            ModelUsage(input_tokens=1)
        usage = ModelUsage.from_payload(
            {"input_tokens": True, "output_tokens": -1, "total_tokens": "3"}
        )
        self.assertEqual(usage.known_calls, 0)
        self.assertEqual(usage.unknown_calls, 1)

    def test_valid_response_succeeds_on_first_attempt(self) -> None:
        provider = FakeProvider([VALID_ANALYSIS])
        result = StructuredOutputService(provider).generate(
            IssueAnalysis, [LLMMessage("user", "Analyze")]
        )
        self.assertEqual(result.attempts, 1)
        self.assertEqual(result.value.problem, "Broken")

    def test_invalid_response_is_repaired_with_bounded_retry(self) -> None:
        provider = FakeProvider(["not json", VALID_ANALYSIS])
        result = StructuredOutputService(provider, maximum_retries=1).generate(
            IssueAnalysis, [LLMMessage("user", "Analyze")]
        )
        self.assertEqual(result.attempts, 2)
        self.assertIn("Validation error", provider.calls[1][-1].content)

    def test_exhaustion_reports_attempt_count(self) -> None:
        provider = FakeProvider(["[]", "{}"])
        with self.assertRaises(StructuredOutputError) as raised:
            StructuredOutputService(provider, maximum_retries=1).generate(
                IssueAnalysis, [LLMMessage("user", "Analyze")]
            )
        self.assertEqual(raised.exception.attempts, 2)

    def test_non_standard_json_and_duplicate_keys_are_rejected(self) -> None:
        responses = [
            VALID_ANALYSIS.replace('"risks":[]', '"risks":[NaN]'),
            VALID_ANALYSIS.replace('"risks":[]', '"risks":[],"risks":[]'),
        ]
        for response in responses:
            with self.subTest(response=response):
                with self.assertRaises(StructuredOutputError):
                    StructuredOutputService(FakeProvider([response]), maximum_retries=0).generate(
                        IssueAnalysis, [LLMMessage("user", "Analyze")]
                    )

    def test_retry_aggregates_reported_and_unknown_usage(self) -> None:
        provider = FakeProvider(
            [
                LLMResponse(
                    content="not json",
                    model="fake-model",
                    usage=ModelUsage.from_payload(
                        {
                            "input_tokens": 7,
                            "output_tokens": 2,
                            "total_tokens": 9,
                        }
                    ),
                    provider_metadata={
                        "reasoning_details": [{"private": "discard this"}]
                    },
                ),
                LLMResponse(content=VALID_ANALYSIS, model="fake-model"),
            ]
        )

        result = StructuredOutputService(provider, maximum_retries=1).generate(
            IssueAnalysis, [LLMMessage("user", "Analyze")]
        )

        self.assertEqual(result.attempts, 2)
        self.assertEqual(result.usage.known_calls, 1)
        self.assertEqual(result.usage.unknown_calls, 1)
        self.assertEqual(result.usage.total_tokens, 9)
        self.assertGreaterEqual(result.latency_ms, 0)
        self.assertFalse(hasattr(result, "provider_metadata"))

    def test_exhaustion_retains_numeric_accounting_only(self) -> None:
        response = LLMResponse(
            content="[]",
            model="fake-model",
            usage=ModelUsage.from_payload(
                {"prompt_tokens": 3, "completion_tokens": 1}
            ),
            provider_metadata={"reasoning_details": ["private"]},
        )

        with self.assertRaises(StructuredOutputError) as raised:
            StructuredOutputService(
                FakeProvider([response]), maximum_retries=0
            ).generate(IssueAnalysis, [LLMMessage("user", "Analyze")])

        self.assertEqual(raised.exception.usage.input_tokens, 3)
        self.assertEqual(raised.exception.usage.output_tokens, 1)
        self.assertEqual(raised.exception.usage.total_tokens_known_calls, 0)
        self.assertFalse(hasattr(raised.exception, "provider_metadata"))


if __name__ == "__main__":
    unittest.main()
