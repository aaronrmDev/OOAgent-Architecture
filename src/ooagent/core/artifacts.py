"""core/artifacts.py — ArtifactFactory, ProvenanceTracker, ResponseDecorator."""

from __future__ import annotations

import time
from collections.abc import Callable

from ooagent.core.protocols import (
    Artifact,
    ArtifactFormat,
    ArtifactPolicy,
    IArtifactFactory,
    InputSpec,
    ProvenanceRecord,
    ResponseDecoratorFn,
    Solution,
    SourceTag,
)

ArtifactBuilder = Callable[[Solution, ArtifactPolicy], str]


class ArtifactFactory(IArtifactFactory):
    """Factory Method — dispatches to format-specific builders — §4 GoF."""

    def __init__(self) -> None:
        self._builders: dict[ArtifactFormat, ArtifactBuilder] = {}

    def register_builder(self, format: ArtifactFormat, builder: ArtifactBuilder) -> None:
        self._builders[format] = builder

    def build(self, solution: Solution, format: ArtifactFormat, policy: ArtifactPolicy) -> Artifact:
        builder = self._builders.get(format)
        content = builder(solution, policy) if builder else solution.content
        return Artifact(
            content=content,
            format=format,
            provenance=[
                ProvenanceRecord(source=s.ref, tag=s.tag, timestamp=time.time())
                for s in solution.sources
            ],
            metadata=solution.metadata,
        )

    def build_error(self, violation: str, ctx: str) -> Artifact:
        return Artifact(
            content=f"[ConstraintViolation]\nContext: {ctx}\n\n{violation}",
            format="text",
            provenance=[],
        )

    def build_missing_inputs(self, missing: list[InputSpec], ctx: str) -> Artifact:
        listing = "\n".join(
            f"{i + 1}. **{inp.name}** ({inp.type}): {inp.description}"
            for i, inp in enumerate(missing)
        )
        return Artifact(
            content=f"[MissingInputs]\nContext: {ctx}\n\nRequired inputs:\n{listing}",
            format="md",
            provenance=[],
        )

    def build_scope_exit(self, ctx: str, query: str) -> Artifact:
        return Artifact(
            content=(
                f'[ScopeExit]\nContext: {ctx}\nQuery: "{query}"\n\n'
                "This query is out of scope for the active context."
            ),
            format="text",
            provenance=[],
        )


class ProvenanceTracker:
    """Pure Fabrication — source / citation discipline — §3 GRASP."""

    def __init__(self) -> None:
        self._records: list[ProvenanceRecord] = []

    def record(self, source: str, tag: SourceTag) -> None:
        self._records.append(ProvenanceRecord(source=source, tag=tag, timestamp=time.time()))

    def dump(self) -> list[ProvenanceRecord]:
        return list(self._records)

    def clear(self) -> None:
        self._records = []


class ResponseDecorator:
    """Decorator — appends citations, units, provenance after solving — §4 GoF."""

    def __init__(self, fns: list[ResponseDecoratorFn] | None = None) -> None:
        self._fns: list[ResponseDecoratorFn] = list(fns or [])

    def add_decorator(self, fn: ResponseDecoratorFn) -> None:
        self._fns.append(fn)

    def apply(self, artifact: Artifact, provenance: list[ProvenanceRecord]) -> Artifact:
        result = artifact
        for fn in self._fns:
            result = fn(result, provenance)
        return result
