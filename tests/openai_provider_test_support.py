from __future__ import annotations

import json
from typing import Mapping

from coding_agent.llm.openai_transport import OpenAIHttpResponse


class QueueTransport:
    def __init__(self, responses: list[OpenAIHttpResponse | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def post(
        self,
        url: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
        maximum_response_bytes: int,
    ) -> OpenAIHttpResponse:
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "payload": json.loads(body),
                "timeout_seconds": timeout_seconds,
                "maximum_response_bytes": maximum_response_bytes,
            }
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def response(status_code: int, payload: object, **headers: str) -> OpenAIHttpResponse:
    return OpenAIHttpResponse(status_code, headers, json.dumps(payload).encode("utf-8"))
