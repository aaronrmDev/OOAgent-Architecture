"""plugins/audit/__init__.py — AuditPlugin.

Contributes a ResponseDecorator that records every completed turn to an
append-only audit log. The audit log is an in-memory ring buffer
(configurable size) plus an optional external sink.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ooagent.core.protocols import (
    Artifact,
    IAgent,
    PluginContributions,
    ProvenanceRecord,
    ResponseDecoratorFn,
)
from ooagent.plugins.base_plugin import AbstractPlugin

_logger = logging.getLogger("ooagent.plugins.audit")


@dataclass(frozen=True)
class AuditEntry:
    turn: int
    agent_id: str
    context_name: str
    format: str
    provenance_sources: list[str]
    content_length: int
    timestamp: str


@dataclass(frozen=True)
class AuditPluginOptions:
    """`max_entries`: max entries kept in the in-memory ring buffer. Default: 1000.
    `sink`: external sink for real-time streaming (e.g. write to file, send to SIEM)."""

    max_entries: int = 1000
    sink: Callable[[AuditEntry], Any] | None = None


class AuditPlugin(AbstractPlugin):
    plugin_id = "ooagent.audit"
    version = "1.0.0"

    def __init__(self, opts: AuditPluginOptions | None = None) -> None:
        opts = opts or AuditPluginOptions()
        self._max_entries = opts.max_entries
        self._sink = opts.sink
        self._log: list[AuditEntry] = []
        self._agent_id = "<unregistered>"
        self._turn = 0

    def on_register(self, agent: "IAgent[Any, Any]") -> None:
        self._agent_id = agent.agent_id

    def on_dispose(self) -> None:
        self._log.clear()

    def contributes(self) -> PluginContributions:
        return PluginContributions(decorators=[self._build_decorator()])

    @property
    def entries(self) -> tuple[AuditEntry, ...]:
        """Immutable snapshot of the audit log."""
        return tuple(self._log)

    def entries_for_context(self, name: str) -> list[AuditEntry]:
        """Returns all audit entries for a given context name."""
        return [e for e in self._log if e.context_name == name]

    def _build_decorator(self) -> ResponseDecoratorFn:
        def decorator(artifact: Artifact, provenance: list[ProvenanceRecord]) -> Artifact:
            self._turn += 1
            context_name = "unknown"
            if artifact.metadata is not None:
                context_name = artifact.metadata.get("contextName", "unknown")

            entry = AuditEntry(
                turn=self._turn,
                agent_id=self._agent_id,
                context_name=context_name,
                format=artifact.format,
                provenance_sources=[f"{p.source} [{p.tag}]" for p in provenance],
                content_length=len(artifact.content),
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

            # Ring buffer — evict oldest on overflow
            if len(self._log) >= self._max_entries:
                self._log.pop(0)
            self._log.append(entry)

            # Fire-and-forget to external sink — never let it crash the turn
            if self._sink is not None:
                self._invoke_sink(entry)

            return artifact

        return decorator

    def _invoke_sink(self, entry: AuditEntry) -> None:
        import asyncio
        import inspect

        try:
            result = self._sink(entry)  # type: ignore[misc]
        except Exception:
            _logger.exception("[AuditPlugin] Sink error")
            return

        if inspect.isawaitable(result):
            task = asyncio.ensure_future(result)

            def _log_if_failed(t: "asyncio.Task[Any]") -> None:
                exc = t.exception() if not t.cancelled() else None
                if exc is not None:
                    _logger.error("[AuditPlugin] Sink error: %s", exc)

            task.add_done_callback(_log_if_failed)
