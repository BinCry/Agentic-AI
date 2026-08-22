"""Small bounded JSON client for the official OpenAI API."""

from __future__ import annotations

import json
import math
import os
import time
from typing import Any, Callable, Mapping
from urllib.error import URLError
from urllib.parse import urlsplit

from .openai_transport import (
    OpenAIClientError,
    OpenAIConfigurationError,
    OpenAIRequestError,
    OpenAIResponseError,
    OpenAITransport,
    UrllibOpenAITransport,
)


class OpenAIHttpClient:
    """Authenticated JSON client with timeout, retry, and redacted errors."""

    RETRYABLE_STATUS_CODES = frozenset({408, 409, 429, 500, 502, 503, 504})

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60.0,
        maximum_retries: int = 2,
        maximum_response_bytes: int = 8_000_000,
        transport: OpenAITransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise OpenAIConfigurationError("OPENAI_API_KEY is required")
        parsed = urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise OpenAIConfigurationError("OpenAI base URL must be an HTTPS origin")
        if (
            not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
            or maximum_retries < 0
            or maximum_retries > 8
        ):
            raise OpenAIConfigurationError("timeout and retry bounds are invalid")
        if maximum_response_bytes < 1:
            raise OpenAIConfigurationError("maximum response size must be positive")
        self._api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.maximum_retries = maximum_retries
        self.maximum_response_bytes = maximum_response_bytes
        self.transport = transport or UrllibOpenAITransport()
        self.sleep = sleep

    @classmethod
    def from_env(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        transport: OpenAITransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> "OpenAIHttpClient":
        values = os.environ if environment is None else environment
        return cls(
            values.get("OPENAI_API_KEY", ""),
            base_url=values.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            timeout_seconds=_float_setting(values, "OPENAI_TIMEOUT_SECONDS", 60.0),
            maximum_retries=_int_setting(values, "OPENAI_MAX_RETRIES", 2),
            transport=transport,
            sleep=sleep,
        )

    def post_json(self, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("API path must start with one slash")
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": "agentic-coding-agent/0.1",
        }
        url = f"{self.base_url}{path}"
        for attempt in range(1, self.maximum_retries + 2):
            try:
                response = self.transport.post(
                    url,
                    headers,
                    body,
                    self.timeout_seconds,
                    self.maximum_response_bytes,
                )
            except (TimeoutError, URLError, OSError) as exc:
                if attempt <= self.maximum_retries:
                    self.sleep(_retry_delay(attempt, None))
                    continue
                message = self._redact(str(exc))[:1_000] or "OpenAI request failed"
                raise OpenAIRequestError(
                    message,
                    retryable=True,
                    attempts=attempt,
                ) from exc

            if 200 <= response.status_code < 300:
                return _decode_object(response.body)
            retryable = response.status_code in self.RETRYABLE_STATUS_CODES
            if retryable and attempt <= self.maximum_retries:
                self.sleep(_retry_delay(attempt, response.headers.get("retry-after")))
                continue
            message = self._redact(_error_message(response.body))
            raise OpenAIRequestError(
                message,
                status_code=response.status_code,
                retryable=retryable,
                attempts=attempt,
            )
        raise AssertionError("unreachable")

    def _redact(self, value: str) -> str:
        return value.replace(self._api_key, "[REDACTED]")[:1_000]


def _decode_object(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body.decode("utf-8"), parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, ValueError) as exc:
        raise OpenAIResponseError("OpenAI response was not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise OpenAIResponseError("OpenAI response must be a JSON object")
    return payload


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _error_message(body: bytes) -> str:
    try:
        payload = _decode_object(body)
        error = payload.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
    except OpenAIResponseError:
        pass
    return "OpenAI request failed"


def _retry_delay(attempt: int, retry_after: str | None) -> float:
    if retry_after:
        try:
            return max(0.0, min(float(retry_after), 30.0))
        except ValueError:
            pass
    return min(float(2 ** (attempt - 1)), 8.0)


def _float_setting(values: Mapping[str, str], name: str, default: float) -> float:
    try:
        return float(values.get(name, str(default)))
    except ValueError as exc:
        raise OpenAIConfigurationError(f"{name} must be numeric") from exc


def _int_setting(values: Mapping[str, str], name: str, default: int) -> int:
    try:
        return int(values.get(name, str(default)))
    except ValueError as exc:
        raise OpenAIConfigurationError(f"{name} must be an integer") from exc
