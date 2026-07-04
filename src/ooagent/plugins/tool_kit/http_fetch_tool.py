"""plugins/tool_kit/http_fetch_tool.py — HttpFetchTool.

Performs GET requests to allowlisted domains and returns response text.
Never fetches arbitrary user-supplied URLs without an allowlist — security
boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx

from ooagent.adapters.tools.base import BaseTool
from ooagent.core.protocols import JSONSchema, ToolExecutionError


@dataclass
class HttpFetchToolOptions:
    """Options accepted by :class:`HttpFetchTool`.

    `allowed_hosts`: Allowlist of hostname patterns (exact match or ending
        wildcard, e.g. '*.example.com'). If empty, all public HTTPS URLs are
        permitted.
    `timeout_ms`: Request timeout in milliseconds. Default: 10 000.
    `max_body_bytes`: Maximum response body size in bytes. Default: 512 000
        (512 KB).
    """

    allowed_hosts: list[str] = field(default_factory=list)
    timeout_ms: int = 10_000
    max_body_bytes: int = 512_000


class HttpFetchTool(BaseTool):
    name = "http_fetch"
    description = "Performs an HTTP GET request and returns the response body as text."

    def __init__(self, opts: HttpFetchToolOptions | None = None) -> None:
        opts = opts or HttpFetchToolOptions()
        self._allowed_hosts = list(opts.allowed_hosts)
        self._timeout_ms = opts.timeout_ms
        self._max_body_bytes = opts.max_body_bytes

    def input_schema(self) -> JSONSchema:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The HTTPS URL to fetch.",
                },
                "headers": {
                    "type": "object",
                    "description": "Optional HTTP request headers as key-value string pairs.",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["url"],
        }

    async def execute(self, args: dict[str, Any]) -> Any:
        url = args.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ToolExecutionError(self.name, args, ValueError("url must be an HTTPS string"))

        if not self._is_allowed(url):
            raise ToolExecutionError(
                self.name,
                args,
                ValueError(f"Host not in allowlist: {urlsplit(url).hostname}"),
            )

        headers = args.get("headers") or {}
        timeout = self._timeout_ms / 1000

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("GET", url, headers=headers) as res:
                    body = await self._read_body(res)
                    return {
                        "status": res.status_code,
                        "contentType": res.headers.get("content-type", "unknown"),
                        "body": body,
                        "url": url,
                    }
        except Exception as err:
            raise ToolExecutionError(self.name, args, err) from err

    async def _read_body(self, res: httpx.Response) -> str:
        chunks: list[bytes] = []
        total = 0
        async for chunk in res.aiter_bytes():
            total += len(chunk)
            if total > self._max_body_bytes:
                await res.aclose()
                return b"".join(chunks).decode("utf-8", errors="replace") + "\n[truncated]"
            chunks.append(chunk)
        return b"".join(chunks).decode("utf-8", errors="replace")

    def _is_allowed(self, url: str) -> bool:
        if not self._allowed_hosts:
            return True
        hostname = urlsplit(url).hostname or ""
        for pattern in self._allowed_hosts:
            if pattern.startswith("*."):
                if hostname.endswith(pattern[1:]):
                    return True
            elif hostname == pattern:
                return True
        return False
