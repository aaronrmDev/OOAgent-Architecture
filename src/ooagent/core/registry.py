"""core/registry.py — ContextRegistry (Singleton), ToolRegistry, PluginRegistry."""

from __future__ import annotations

import logging
from collections.abc import Callable

from ooagent.core.protocols import (
    AntiPattern,
    ArtifactPolicy,
    IDomainContext,
    InputSpec,
    Invariant,
    IPlugin,
    ISolver,
    ITool,
    LifecycleError,
    PipelineStep,
    ProblemClass,
    Query,
    Term,
)

_logger = logging.getLogger("ooagent.registry")


def _create_inline_null_context() -> IDomainContext:
    """Inline minimal NullContext — avoids circular dependency with contexts/.
    The full NullContext class lives in contexts/null_context.py."""

    class _InlineNullContext(IDomainContext):
        @property
        def name(self) -> str:
            return "NullContext"

        @property
        def version(self) -> str:
            return "1.0"

        def vocabulary(self) -> set[Term]:
            return set()

        def problem_classes(self) -> set[ProblemClass]:
            return set()

        def solvers(self) -> dict[str, ISolver]:
            return {}

        def invariants(self) -> list[Invariant]:
            return []

        def pipeline(self) -> list[PipelineStep]:
            return []

        def anti_patterns(self) -> list[AntiPattern]:
            return []

        def required_inputs(self, pc: ProblemClass) -> list[InputSpec]:
            return []

        def artifact_preferences(self) -> ArtifactPolicy:
            return ArtifactPolicy(
                preferred_formats=["text"],
                type_hints_required=False,
                comment_policy="none",
            )

        def system_prompt_extension(self) -> str:
            return "NullContext v1.0 is active. Do not make domain-specific claims."

        def resolve_intent(self, query: Query) -> ProblemClass | None:
            return None

    return _InlineNullContext()


class ContextRegistry:
    """Singleton — single source of truth for active IDomainContext — §4 GoF."""

    _instance: ContextRegistry | None = None

    def __init__(self) -> None:
        self._contexts: dict[str, IDomainContext] = {}
        self._null_context_factory: Callable[[], IDomainContext] = _create_inline_null_context
        self._threshold = 0.1

    @classmethod
    def get_instance(cls) -> ContextRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Test hook."""
        cls._instance = None

    def set_null_context_factory(self, factory: Callable[[], IDomainContext]) -> None:
        self._null_context_factory = factory

    def set_threshold(self, threshold: float) -> None:
        self._threshold = threshold

    def register(self, context: IDomainContext) -> None:
        key = f"{context.name}@{context.version}"
        self._contexts[key] = context

    def resolve(self, query: Query) -> IDomainContext:
        """Context resolution algorithm — §9 CLAUDE.md."""
        best_score = -1.0
        best_context: IDomainContext | None = None
        tie_version = ""

        for ctx in self._contexts.values():
            score = self._score(query, ctx)
            if score > best_score:
                best_score = score
                best_context = ctx
                tie_version = ctx.version
            elif score == best_score and score > 0 and ctx.version > tie_version:
                best_context = ctx
                tie_version = ctx.version

        if best_context is None or best_score < self._threshold:
            return self._null_context_factory()
        return best_context

    @property
    def registered_names(self) -> list[str]:
        return [f"{c.name} v{c.version}" for c in self._contexts.values()]

    def _score(self, query: Query, ctx: IDomainContext) -> float:
        text = query.text.lower()
        score = 0.0

        for term in ctx.vocabulary():
            if term.label.lower() in text:
                score += 2 if term.canonical else 1
        for pc in ctx.problem_classes():
            if pc.name.lower() in text:
                score += 3
        if ctx.resolve_intent(query) is not None:
            score += 5
        return score


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ITool] = {}

    def register(self, tool: ITool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ITool | None:
        return self._tools.get(name)

    def all(self) -> list[ITool]:
        return list(self._tools.values())

    def has(self, name: str) -> bool:
        return name in self._tools


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, IPlugin] = {}

    def register(self, plugin: IPlugin) -> None:
        key = f"{plugin.plugin_id}@{plugin.version}"
        if key in self._plugins:
            raise ValueError(f"Duplicate plugin registration: {key}")
        self._plugins[key] = plugin

    def verify(self) -> None:
        """Calls IPlugin.self_check() on every registered plugin — §6
        CLAUDE.md LifecycleManager responsibility 2 ("PluginRegistry.verify()")."""
        for plugin in self._plugins.values():
            if not plugin.self_check():
                raise LifecycleError(f"Plugin failed self-check: {plugin.plugin_id}")

    async def dispose_all(self) -> None:
        for plugin in self._plugins.values():
            try:
                plugin.on_dispose()
            except Exception:
                # Isolate plugin failures — never crash the agent — §16 CLAUDE.md
                _logger.exception("[PluginRegistry] Dispose failed for %s", plugin.plugin_id)

    def all(self) -> list[IPlugin]:
        return list(self._plugins.values())
