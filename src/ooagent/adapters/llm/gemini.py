"""adapters/llm/gemini.py — ILLMClient -> Google Gemini API."""

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
)


@dataclass(frozen=True)
class GeminiConfig:
    api_key: str
    model: str | None = None
    max_tokens: int | None = None
    base_url: str | None = None


class GeminiLLMClient(ILLMClient):
    """ILLMClient adapter for the Google Gemini API."""

    def __init__(self, config: GeminiConfig) -> None:
        self._api_key = config.api_key
        self._model_id = config.model if config.model is not None else "gemini-1.5-pro"
        self._max_tokens = config.max_tokens if config.max_tokens is not None else 8192
        self._base_url = (
            config.base_url
            if config.base_url is not None
            else "https://generativelanguage.googleapis.com"
        )

    @property
    def vendor(self) -> LLMVendor:
        return "gemini"

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

        url = f"{self._base_url}/v1beta/models/{self.model_id}:generateContent?key={self._api_key}"
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json=self._build_body(request),
            )

        if response.status_code >= 400:
            raise RuntimeError(f"Gemini API error: {response.status_code} {response.reason_phrase}")

        return self._parse(response.json())

    async def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]:
        url = (
            f"{self._base_url}/v1beta/models/{self.model_id}:streamGenerateContent"
            f"?key={self._api_key}&alt=sse"
        )
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                url,
                headers={"Content-Type": "application/json"},
                json=self._build_body(request),
            ) as response:
                if response.status_code >= 400:
                    raise RuntimeError(f"Gemini stream error: {response.status_code}")

                decoder = codecs.getincrementaldecoder("utf-8")()
                async for raw in response.aiter_bytes():
                    text = decoder.decode(raw)
                    for line in text.split("\n"):
                        if not line.startswith("data: "):
                            continue
                        try:
                            event = json.loads(line[6:])
                        except json.JSONDecodeError:
                            continue  # skip malformed events
                        candidates = event.get("candidates") or []
                        parts = (
                            (candidates[0].get("content") or {}).get("parts")
                            if candidates
                            else None
                        ) or []
                        part_text = parts[0].get("text") if parts else None
                        if part_text:
                            yield CompletionChunk(delta=part_text, done=False)
        yield CompletionChunk(delta="", done=True)

    def _build_body(self, request: CompletionRequest) -> dict[str, Any]:
        system_msg = next((m for m in request.messages if m.role == "system"), None)
        user_messages = [m for m in request.messages if m.role != "system"]

        contents = [
            {
                "role": "model" if m.role == "assistant" else "user",
                "parts": [{"text": m.content}],
            }
            for m in user_messages
        ]

        generation_config: dict[str, Any] = {
            "maxOutputTokens": (
                request.max_tokens if request.max_tokens is not None else self.max_tokens
            ),
        }
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature
        if request.stop_sequences:
            generation_config["stopSequences"] = request.stop_sequences

        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
        }
        if system_msg:
            body["systemInstruction"] = {"parts": [{"text": system_msg.content}]}
        if request.tools:
            body["tools"] = request.tools
        return body

    def _parse(self, data: dict[str, Any]) -> CompletionResponse:
        candidates = data.get("candidates") or []
        candidate = candidates[0] if candidates else None
        parts = (candidate.get("content") or {}).get("parts", []) if candidate else []
        text = "".join(p.get("text", "") for p in parts)

        finish_reason = candidate.get("finishReason") if candidate else None
        stop_reason: Literal["end_turn", "max_tokens", "tool_use", "stop_sequence"] = (
            "max_tokens" if finish_reason == "MAX_TOKENS" else "end_turn"
        )

        usage_metadata = data.get("usageMetadata") or {}
        return CompletionResponse(
            content=text,
            stop_reason=stop_reason,
            usage=TokenUsage(
                input_tokens=usage_metadata.get("promptTokenCount", 0),
                output_tokens=usage_metadata.get("candidatesTokenCount", 0),
            ),
        )

    def _estimate_tokens(self, request: CompletionRequest) -> int:
        return math.ceil(sum(len(m.content) for m in request.messages) / 4)
