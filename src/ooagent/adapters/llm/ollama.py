"""adapters/llm/ollama.py — ILLMClient -> Ollama local API (OpenAI-compatible)."""

from __future__ import annotations

import codecs
import json
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
    TokenUsage,
)


@dataclass(frozen=True)
class OllamaConfig:
    model: str | None = None
    max_tokens: int | None = None
    base_url: str | None = None


class OllamaLLMClient(ILLMClient):
    """ILLMClient adapter for the Ollama local API."""

    def __init__(self, config: OllamaConfig | None = None) -> None:
        config = config if config is not None else OllamaConfig()
        self._model_id = config.model if config.model is not None else "llama3.3"
        self._max_tokens = config.max_tokens if config.max_tokens is not None else 4096
        self._base_url = (
            config.base_url if config.base_url is not None else "http://localhost:11434"
        )

    @property
    def vendor(self) -> LLMVendor:
        return "ollama"

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    @property
    def supports_tools(self) -> bool:
        return False

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/v1/chat/completions",
                headers={"Content-Type": "application/json"},
                json=self._build_body(request),
            )

        if response.status_code >= 400:
            raise RuntimeError(f"Ollama API error: {response.status_code} {response.reason_phrase}")

        return self._parse(response.json())

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]:
        body = {**self._build_body(request), "stream": True}
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/v1/chat/completions",
                headers={"Content-Type": "application/json"},
                json=body,
            ) as response:
                if response.status_code >= 400:
                    raise RuntimeError(f"Ollama stream error: {response.status_code}")

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

    def _build_body(self, request: CompletionRequest) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model_id,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }
        if request.max_tokens:
            body["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            body["temperature"] = request.temperature
        return body

    def _parse(self, data: dict[str, Any]) -> CompletionResponse:
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("Ollama returned no choices")
        choice = choices[0]
        message = choice.get("message", {})

        finish_reason = choice.get("finish_reason")
        stop_reason: Literal["end_turn", "max_tokens", "tool_use", "stop_sequence"] = (
            "max_tokens" if finish_reason == "length" else "end_turn"
        )

        usage = data.get("usage") or {}
        return CompletionResponse(
            content=message.get("content", ""),
            stop_reason=stop_reason,
            usage=TokenUsage(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
            ),
        )
