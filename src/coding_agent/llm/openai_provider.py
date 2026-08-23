"""OpenAI Responses API adapter for the provider-neutral LLM contract."""

from __future__ import annotations

import os
from typing import Any, Mapping, Sequence

from .openai_client import OpenAIConfigurationError, OpenAIHttpClient, OpenAIResponseError
from .provider import LLMMessage, LLMResponse, ModelUsage


class OpenAIResponsesProvider:
    provider_name = "openai-responses"

    def __init__(
        self,
        client: OpenAIHttpClient,
        *,
        model: str = "gpt-5.6",
        reasoning_effort: str | None = "medium",
        maximum_output_tokens: int = 8_000,
    ) -> None:
        if not model.strip():
            raise OpenAIConfigurationError("OpenAI model must not be empty")
        if reasoning_effort not in {None, "none", "low", "medium", "high", "xhigh", "max"}:
            raise OpenAIConfigurationError("OpenAI reasoning effort is invalid")
        if maximum_output_tokens < 1 or maximum_output_tokens > 128_000:
            raise OpenAIConfigurationError("maximum output tokens must be between 1 and 128000")
        self.client = client
        self.model = model.strip()
        self.reasoning_effort = reasoning_effort
        self.maximum_output_tokens = maximum_output_tokens

    @classmethod
    def from_env(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        client: OpenAIHttpClient | None = None,
    ) -> "OpenAIResponsesProvider":
        values = os.environ if environment is None else environment
        effort = values.get("OPENAI_REASONING_EFFORT", "medium").strip().lower()
        return cls(
            client or OpenAIHttpClient.from_env(values),
            model=values.get("OPENAI_MODEL", "gpt-5.6"),
            reasoning_effort=effort or None,
            maximum_output_tokens=_output_token_setting(values),
        )

    def complete(self, messages: Sequence[LLMMessage]) -> LLMResponse:
        if not messages:
            raise ValueError("at least one LLM message is required")
        allowed_roles = {"developer", "system", "user", "assistant"}
        inputs: list[dict[str, str]] = []
        for message in messages:
            if message.role not in allowed_roles or not message.content:
                raise ValueError("LLM messages require a supported role and non-empty content")
            inputs.append({"role": message.role, "content": message.content})
        request: dict[str, Any] = {
            "model": self.model,
            "input": inputs,
            "max_output_tokens": self.maximum_output_tokens,
            "store": False,
        }
        if self.reasoning_effort is not None:
            request["reasoning"] = {"effort": self.reasoning_effort}
        payload = self.client.post_json("/responses", request)
        content = _response_text(payload)
        model = payload.get("model")
        if not isinstance(model, str) or not model:
            raise OpenAIResponseError("Responses API result omitted the model")
        status = payload.get("status")
        return LLMResponse(
            content=content,
            model=model,
            finish_reason=status if isinstance(status, str) else None,
            usage=ModelUsage.from_payload(payload.get("usage")),
            provider_metadata={"response_id": payload.get("id")},
        )


def _response_text(payload: Mapping[str, Any]) -> str:
    output = payload.get("output")
    if not isinstance(output, list):
        raise OpenAIResponseError("Responses API result omitted output items")
    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") == "output_text":
                text = part.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
    if not parts:
        raise OpenAIResponseError("Responses API result contained no output text")
    return "".join(parts)


def _output_token_setting(values: Mapping[str, str]) -> int:
    try:
        return int(values.get("OPENAI_MAX_OUTPUT_TOKENS", "8000"))
    except ValueError as exc:
        raise OpenAIConfigurationError("OPENAI_MAX_OUTPUT_TOKENS must be an integer") from exc
