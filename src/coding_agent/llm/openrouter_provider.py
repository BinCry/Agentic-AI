"""OpenRouter adapter for the provider-neutral LLM contract."""

from __future__ import annotations

import os
from typing import Mapping

from .openai_client import OpenAIHttpClient
from .openai_provider import OpenAIResponsesProvider
from .openai_transport import OpenAIConfigurationError, OpenAITransport


class OpenRouterConfigurationError(OpenAIConfigurationError):
    """Raised when required OpenRouter configuration is absent or invalid."""


class OpenRouterResponsesProvider(OpenAIResponsesProvider):
    """Bounded OpenRouter Responses API adapter using the shared HTTPS stack."""

    provider_name = "openrouter-responses"

    @classmethod
    def from_env(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        transport: OpenAITransport | None = None,
    ) -> "OpenRouterResponsesProvider":
        values = os.environ if environment is None else environment
        api_key = values.get("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise OpenRouterConfigurationError("OPENROUTER_API_KEY is required")
        try:
            client = OpenAIHttpClient(
                api_key,
                base_url=values.get(
                    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
                ),
                timeout_seconds=_float_setting(
                    values, "OPENROUTER_TIMEOUT_SECONDS", 60.0
                ),
                maximum_retries=_int_setting(values, "OPENROUTER_MAX_RETRIES", 2),
                transport=transport,
            )
            effort = values.get("OPENROUTER_REASONING_EFFORT", "medium").strip().lower()
            return cls(
                client,
                model=values.get("OPENROUTER_MODEL", "stealth/ox-alpha"),
                reasoning_effort=effort or None,
                maximum_output_tokens=_int_setting(
                    values, "OPENROUTER_MAX_OUTPUT_TOKENS", 8_000
                ),
            )
        except OpenRouterConfigurationError:
            raise
        except OpenAIConfigurationError as exc:
            message = str(exc).replace("OpenAI", "OpenRouter")
            raise OpenRouterConfigurationError(message) from exc


def _float_setting(values: Mapping[str, str], name: str, default: float) -> float:
    try:
        return float(values.get(name, str(default)))
    except ValueError as exc:
        raise OpenRouterConfigurationError(f"{name} must be numeric") from exc


def _int_setting(values: Mapping[str, str], name: str, default: int) -> int:
    try:
        return int(values.get(name, str(default)))
    except ValueError as exc:
        raise OpenRouterConfigurationError(f"{name} must be an integer") from exc
