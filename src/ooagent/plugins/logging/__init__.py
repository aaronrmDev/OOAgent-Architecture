"""plugins/logging/__init__.py — LoggingPlugin.

Contributes a ResponseDecorator that appends a provenance/log footer to
every artifact.

Note on the package name: this subpackage is named `logging` to mirror the
TypeScript source's `plugins/logging/` directory. This is safe in Python —
absolute-import resolution means `ooagent.plugins.logging` never shadows
the standard-library `logging` module.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from ooagent.core.protocols import (
    Artifact,
    IAgent,
    PluginContributions,
    ProvenanceRecord,
    ResponseDecoratorFn,
)
from ooagent.plugins.base_plugin import AbstractPlugin


def _default_sink(line: str) -> None:
    print(line)


@dataclass(frozen=True)
class LoggingPluginOptions:
    """`prefix`: written before each log line. Default: '[OOAgent]'.
    `include_provenance`: whether to include full provenance records in the
    footer. Default: True.
    `sink`: custom sink — defaults to `print`."""

    prefix: str = "[OOAgent]"
    include_provenance: bool = True
    sink: Callable[[str], None] = _default_sink


class LoggingPlugin(AbstractPlugin):
    plugin_id = "ooagent.logging"
    version = "1.0.0"

    def __init__(self, opts: LoggingPluginOptions | None = None) -> None:
        opts = opts or LoggingPluginOptions()
        self._prefix = opts.prefix
        self._include_provenance = opts.include_provenance
        self._sink = opts.sink
        self._agent_id = "<unregistered>"

    def on_register(self, agent: IAgent[Any, Any]) -> None:
        self._agent_id = agent.agent_id
        self._sink(f"{self._prefix} LoggingPlugin registered on agent {self._agent_id}")

    def on_dispose(self) -> None:
        self._sink(f"{self._prefix} LoggingPlugin disposed for agent {self._agent_id}")

    def contributes(self) -> PluginContributions:
        return PluginContributions(decorators=[self._build_decorator()])

    def _build_decorator(self) -> ResponseDecoratorFn:
        prefix = self._prefix
        include_provenance = self._include_provenance
        sink = self._sink

        def decorator(artifact: Artifact, provenance: list[ProvenanceRecord]) -> Artifact:
            timestamp = datetime.now(UTC).isoformat()
            sink(f"{prefix} [{timestamp}] turn complete — format={artifact.format}")

            if not include_provenance or len(provenance) == 0:
                return artifact

            footer = "\n".join(f"<!-- source: {p.source} [{p.tag}] -->" for p in provenance)

            return replace(artifact, content=f"{artifact.content}\n\n{footer}")

        return decorator
