"""Bounded HTTPS transport and typed failures for OpenAI adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class OpenAIClientError(RuntimeError):
    """Base class for configuration, request, and response failures."""


class OpenAIConfigurationError(OpenAIClientError):
    """Raised when required provider configuration is absent or invalid."""


class OpenAIRequestError(OpenAIClientError):
    """Raised after a request fails or exhausts bounded retries."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
        attempts: int = 1,
    ) -> None:
        self.status_code = status_code
        self.retryable = retryable
        self.attempts = attempts
        super().__init__(message)


class OpenAIResponseError(OpenAIClientError):
    """Raised when a successful API response violates its expected contract."""


@dataclass(slots=True, frozen=True)
class OpenAIHttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


class OpenAITransport(Protocol):
    def post(
        self,
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
        maximum_response_bytes: int,
    ) -> OpenAIHttpResponse: ...


class UrllibOpenAITransport:
    """Dependency-free HTTPS transport with bounded response reads."""

    def __init__(self) -> None:
        self._opener = build_opener(_RejectRedirectHandler())

    def post(
        self,
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
        maximum_response_bytes: int,
    ) -> OpenAIHttpResponse:
        request = Request(url, data=body, headers=dict(headers), method="POST")
        try:
            with self._opener.open(request, timeout=timeout_seconds) as response:
                payload = response.read(maximum_response_bytes + 1)
                return OpenAIHttpResponse(
                    response.status,
                    {key.lower(): value for key, value in response.headers.items()},
                    _bounded_body(payload, maximum_response_bytes),
                )
        except HTTPError as exc:
            payload = exc.read(maximum_response_bytes + 1)
            headers = exc.headers.items() if exc.headers is not None else ()
            return OpenAIHttpResponse(
                exc.code,
                {key.lower(): value for key, value in headers},
                _bounded_body(payload, maximum_response_bytes),
            )


def _bounded_body(body: bytes, maximum_bytes: int) -> bytes:
    if len(body) > maximum_bytes:
        raise OpenAIResponseError("OpenAI response exceeded the configured size limit")
    return body


class _RejectRedirectHandler(HTTPRedirectHandler):
    """Prevent authorization headers from crossing redirect boundaries."""

    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None
