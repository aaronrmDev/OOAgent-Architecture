"""adapters/llm/anthropic.py — ILLMClient -> Anthropic Messages API."""

from __future__ import annotations

import codecs
import json
import math
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

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
class AnthropicConfig:
    api_key: str
    model: str | None = None
    max_tokens: int | None = None
    base_url: str | None = None


class AnthropicLLMClient(ILLMClient):
    """ILLMClient adapter for the Anthropic Messages API."""

    def __init__(self, config: AnthropicConfig) -> None:
        self._api_key = config.api_key
        self._model_id = config.model if config.model is not None else "claude-opus-4-6"
        self._max_tokens = config.max_tokens if config.max_tokens is not None else 8192
        self._base_url = (
            config.base_url if config.base_url is not None else "https://api.anthropic.com"
        )

    @property
    def vendor(self) -> LLMVendor:
        return "anthropic"

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
                f"{self._base_url}/v1/messages",
                headers=self._headers(),
                json=self._build_body(request),
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Anthropic API error: {response.status_code} {response.reason_phrase}"
            )

        return self._parse(response.json())

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]:
        body = {**self._build_body(request), "stream": True}
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/v1/messages",
                headers=self._headers(),
                json=body,
            ) as response:
                if response.status_code >= 400:
                    raise RuntimeError(f"Anthropic stream error: {response.status_code}")

                decoder = codecs.getincrementaldecoder("utf-8")()
                async for raw in response.aiter_bytes():
                    text = decoder.decode(raw)
                    for line in text.split("\n"):
                        if not line.startswith("data: "):
                            continue
                        payload = line[6:]
                        if payload.strip() == "[DONE]":
                            yield CompletionChunk(delta="", done=True)
                            return
                        try:
                            event = json.loads(payload)
                        except json.JSONDecodeError:
                            continue  # skip malformed events
                        if event.get("type") == "content_block_delta":
                            delta_text = (event.get("delta") or {}).get("text")
                            if delta_text:
                                yield CompletionChunk(delta=delta_text, done=False)
        yield CompletionChunk(delta="", done=True)

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
        }

    def _build_body(self, request: CompletionRequest) -> dict[str, Any]:
        system = next((m.content for m in request.messages if m.role == "system"), None)
        messages = [
            {"role": m.role, "content": m.content}
            for m in request.messages
            if m.role != "system"
        ]

        body: dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": (
                request.max_tokens if request.max_tokens is not None else self.max_tokens
            ),
            "messages": messages,
        }
        if system:
            body["system"] = system
        if request.tools:
            body["tools"] = request.tools
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.stop_sequences:
            body["stop_sequences"] = request.stop_sequences
        return body

    def _parse(self, data: dict[str, Any]) -> CompletionResponse:
        content_blocks = data.get("content", [])
        text_block = next((b for b in content_blocks if b.get("type") == "text"), None)
        tool_blocks = [b for b in content_blocks if b.get("type") == "tool_use"]

        stop_reason_raw = data.get("stop_reason")
        if stop_reason_raw == "tool_use":
            stop_reason = "tool_use"
        elif stop_reason_raw == "max_tokens":
            stop_reason = "max_tokens"
        else:
            stop_reason = "end_turn"

        usage = data.get("usage", {})
        return CompletionResponse(
            content=text_block.get("text", "") if text_block else "",
            stop_reason=stop_reason,
            usage=TokenUsage(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
            ),
            tool_calls=[
                ToolCall(id=b.get("id", ""), name=b.get("name", ""), args=b.get("input") or {})
                for b in tool_blocks
            ],
        )

    def _estimate_tokens(self, request: CompletionRequest) -> int:
        chars = sum(len(m.content) for m in request.messages)
        return math.ceil(chars / 4)
