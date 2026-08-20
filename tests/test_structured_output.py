from __future__ import annotations

import unittest
from collections.abc import Sequence

from coding_agent.llm.provider import LLMMessage, LLMResponse
from coding_agent.llm.structured_output import StructuredOutputError, StructuredOutputService
from coding_agent.models.decisions import IssueAnalysis


VALID_ANALYSIS = (
    '{"task_type":"bug_fix","problem":"Broken",'
    '"expected_behavior":"Works","acceptance_criteria":["Passes"],'
    '"search_queries":[],"risks":[]}'
)


class FakeProvider:
    provider_name = "fake"

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[list[LLMMessage]] = []

    def complete(self, messages: Sequence[LLMMessage]) -> LLMResponse:
        self.calls.append(list(messages))
        return LLMResponse(content=self.responses.pop(0), model="fake-model")


class StructuredOutputTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
