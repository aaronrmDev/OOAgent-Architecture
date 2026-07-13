"""adapters/llm/openai.py — ILLMClient -> OpenAI Chat Completions API."""

from __future__ import annotations

import codecs
import json
import math
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from ooagent.core.protocols import (
    CompletionChunk,
    CompletionRequest,
    CompletionResponse,
    ILLMClient,
    LLMVendor,
    TokenLimitError,
    TokenUsage,
    ToolCall,
)


@dataclass(frozen=True)
class OpenAIConfig:
    api_key: str
    model: str | None = None
    max_tokens: int | None = None
    base_url: str | None = None


class OpenAILLMClient(ILLMClient):
    """ILLMClient adapter for the OpenAI Chat Completions API."""

    def __init__(self, config: OpenAIConfig) -> None:
        self._api_key = config.api_key
        self._model_id = config.model if config.model is not None else "gpt-4o"
        self._max_tokens = config.max_tokens if config.max_tokens is not None else 4096
        self._base_url = (
            config.base_url if config.base_url is not None else "https://api.openai.com"
        )

    @property
    def vendor(self) -> LLMVendor:
        return "openai"

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    @property
    def supports_tools(self) -> bool:
        return True

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        estimated = self._estimate_tokens(request)
        if estimated > self.max_tokens:
            raise TokenLimitError(estimated, self.max_tokens)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/v1/chat/completions",
                headers=self._headers(),
                json=self._build_body(request),
            )

        if response.status_code >= 400:
            raise RuntimeError(f"OpenAI API error: {response.status_code} {response.reason_phrase}")

        return self._parse(response.json())

    async def ping(self) -> bool:
        return True

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]:
        body = {**self._build_body(request), "stream": True}
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/v1/chat/completions",
                headers=self._headers(),
                json=body,
            ) as response:
                if response.status_code >= 400:
                    raise RuntimeError(f"OpenAI stream error: {response.status_code}")

                decoder = codecs.getincrementaldecoder("utf-8")()
                async for raw in response.aiter_bytes():
                    text = decoder.decode(raw)
                    for line in text.split("\n"):
                        if not line.startswith("data: "):
                            continue
                        payload = line[6:].strip()
                        if payload == "[DONE]":
                            yield CompletionChunk(delta="", done=True)
                            return
                        try:
                            event = json.loads(payload)
                        except json.JSONDecodeError:
                            continue  # skip malformed events
                        choices = event.get("choices") or []
                        delta = (choices[0].get("delta") if choices else None) or {}
                        content = delta.get("content")
                        if content:
                            yield CompletionChunk(delta=content, done=False)
        yield CompletionChunk(delta="", done=True)

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

    def _build_body(self, request: CompletionRequest) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": (
                request.max_tokens if request.max_tokens is not None else self.max_tokens
            ),
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }
        if request.tools:
            body["tools"] = request.tools
            body["tool_choice"] = "auto"
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.stop_sequences:
            body["stop"] = request.stop_sequences
        return body

    def _parse(self, data: dict[str, Any]) -> CompletionResponse:
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("OpenAI returned no choices")
        choice = choices[0]
        message = choice.get("message", {})

        raw_tool_calls = message.get("tool_calls")
        tool_calls = None
        if raw_tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    args=json.loads(tc["function"]["arguments"]),
                )
                for tc in raw_tool_calls
            ]

        finish_reason = choice.get("finish_reason")
        stop_reason: Literal["end_turn", "max_tokens", "tool_use", "stop_sequence"]
        if finish_reason == "tool_calls":
            stop_reason = "tool_use"
        elif finish_reason == "length":
            stop_reason = "max_tokens"
        else:
            stop_reason = "end_turn"

        usage = data.get("usage", {})
        return CompletionResponse(
            content=message.get("content") or "",
            stop_reason=stop_reason,
            usage=TokenUsage(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
            ),
            tool_calls=tool_calls,
        )

    def _estimate_tokens(self, request: CompletionRequest) -> int:
        return math.ceil(sum(len(m.content) for m in request.messages) / 4)
