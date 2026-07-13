"""core/agent.py — AbstractAgent, LLMAgent, OOAgent (composition root, Template Method)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Generic

from ooagent.core.artifacts import ArtifactFactory, ProvenanceTracker, ResponseDecorator
from ooagent.core.lifecycle import LifecycleManager
from ooagent.core.pipeline import (
    ConstraintEngine,
    ResponsePipeline,
    empty_query_step,
)
from ooagent.core.protocols import (
    AgentConfig,
    Artifact,
    ArtifactFormat,
    Command,
    CompletionRequest,
    ConstraintViolationError,
    IAgent,
    IDomainContext,
    ILLMClient,
    ISessionState,
    ISolver,
    ITelemetryProvider,
    LifecycleError,
    Message,
    Query,
    ScopeExitError,
    Solution,
    SourceRecord,
    T,
    ToolCall,
    TQuery,
    TResponse,
)
from ooagent.core.registry import ContextRegistry, PluginRegistry, ToolRegistry
from ooagent.core.state import SessionState

_logger = logging.getLogger("ooagent.agent")


class _SolverDispatcher:
    """Strategy: solver dispatch — selects ISolver per ProblemClass."""

    def select(self, problem_class: str, context: IDomainContext) -> ISolver | None:
        return context.solvers().get(problem_class)


class AbstractAgent(IAgent[TQuery, TResponse], Generic[TQuery, TResponse]):
    """Abstract base — root interface implementation."""

    def __init__(self, id: str | None = None) -> None:
        self._agent_id = id or str(uuid.uuid4())

    @property
    def agent_id(self) -> str:
        return self._agent_id


class LLMAgent(AbstractAgent[TQuery, TResponse], Generic[TQuery, TResponse]):
    """LLM-backed abstract — adds ILLMClient."""

    def __init__(self, llm_client: ILLMClient, id: str | None = None) -> None:
        super().__init__(id)
        self._llm_client = llm_client


class _NullTelemetry(ITelemetryProvider):
    """Null Object for telemetry — used when no provider is injected."""

    async def span(self, name: str, fn: Callable[[], Awaitable[T]]) -> T:
        return await fn()

    def counter(self, name: str, delta: float = 1) -> None:
        return None

    def gauge(self, name: str, value: float) -> None:
        return None

    def histogram(self, name: str, value: float) -> None:
        return None

    def event(self, name: str, payload: dict[str, Any]) -> None:
        return None


NULL_TELEMETRY = _NullTelemetry()


class OOAgent(LLMAgent[Query, Artifact]):
    """OOAgent — concrete composition root."""

    def __init__(
        self,
        llm_client: ILLMClient,
        ctx_registry: ContextRegistry | None = None,
        tool_registry: ToolRegistry | None = None,
        plugin_registry: PluginRegistry | None = None,
        pipeline: ResponsePipeline | None = None,
        constraint_engine: ConstraintEngine | None = None,
        artifact_factory: ArtifactFactory | None = None,
        decorator: ResponseDecorator | None = None,
        telemetry: ITelemetryProvider | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(llm_client, id)
        self._state = SessionState()
        self._ctx_registry = ctx_registry or ContextRegistry.get_instance()
        self._tool_registry = tool_registry or ToolRegistry()
        self._plugin_registry = plugin_registry or PluginRegistry()
        self._pipeline = pipeline or ResponsePipeline([empty_query_step()])
        self._constraint_engine = constraint_engine or ConstraintEngine.get_instance()
        self._artifact_factory = artifact_factory or ArtifactFactory()
        self._decorator = decorator or ResponseDecorator()
        self._provenance = ProvenanceTracker()
        self._telemetry = telemetry or NULL_TELEMETRY
        self._solver_dispatcher = _SolverDispatcher()
        self._lifecycle = LifecycleManager(self._plugin_registry, self._state, llm_client)
        self._config: AgentConfig | None = None

    @property
    def state(self) -> ISessionState:
        return self._state

    @property
    def is_ready(self) -> bool:
        return self._lifecycle.is_ready

    async def initialize(self, config: AgentConfig) -> None:
        self._config = config
        await self._lifecycle.initialize(config)

        for plugin in self._plugin_registry.all():
            try:
                plugin.on_register(self)
                contributions = plugin.contributes()
                for tool in contributions.tools or []:
                    self._tool_registry.register(tool)
                for ctx in contributions.contexts or []:
                    self._ctx_registry.register(ctx)
                for dec in contributions.decorators or []:
                    self._decorator.add_decorator(dec)
            except Exception:
                _logger.exception("[OOAgent] Plugin registration failed: %s", plugin.plugin_id)

    async def dispose(self) -> None:
        await self._lifecycle.dispose()

    async def respond(self, query: Query) -> Artifact:
        """Template Method — §10 CLAUDE.md."""
        if not self._lifecycle.is_ready:
            raise LifecycleError("Agent is not ready. Call initialize() first.")

        async def _turn() -> Artifact:
            self._provenance.clear()
            self._state.transition("GATHERING")

            try:
                context = self._ctx_registry.resolve(query)
                self._state.set_context(context.name)
                pipeline = self._pipeline.extend(context.pipeline())
                snapshot = self._state.snapshot()
            except Exception as err:
                return self._handle_failure(err, None, "")

            self._state.transition("MODELING")
            try:
                extras = await pipeline.run(query, context)
            except Exception as err:
                return self._handle_failure(err, context, snapshot.id)

            self._state.transition("SOLVING")
            try:
                solution = await self._solve(query, context, extras)
            except Exception as err:
                return self._handle_failure(err, context, snapshot.id)

            self._state.transition("VALIDATING")
            try:
                self._constraint_engine.assert_all(solution, context.invariants())
            except Exception as err:
                return self._handle_failure(err, context, snapshot.id)

            self._state.transition("DELIVERING")
            try:
                format: ArtifactFormat = (
                    query.format
                    or (context.artifact_preferences().preferred_formats or ["text"])[0]
                )
                artifact = self._artifact_factory.build(
                    solution, format, context.artifact_preferences()
                )
                enriched = self._decorator.apply(artifact, self._provenance.dump())

                cmd = Command(
                    id=str(uuid.uuid4()),
                    query=query,
                    solution=solution,
                    context_name=context.name,
                    trace=self._state.trace,
                    timestamp=time.time(),
                )
                self._state.commit(cmd)
                self._state.reset()

                self._telemetry.event(
                    "turn.complete",
                    {"context": context.name, "format": format, "turn": self._state.turn},
                )

                self._lifecycle.record_llm_success()
                return enriched
            except Exception as err:
                return self._handle_unrecoverable_failure(err, context)

        return await self._telemetry.span("agent.turn", _turn)

    async def _solve(
        self, query: Query, context: IDomainContext, extras: dict[str, Any]
    ) -> Solution:
        problem_class = context.resolve_intent(query)
        if problem_class:
            solver = self._solver_dispatcher.select(problem_class.solver, context)
            if solver:
                return await solver.solve(query, context)

        return await self._llm_tool_loop(query, context, extras)

    async def _llm_tool_loop(
        self, query: Query, context: IDomainContext, extras: dict[str, Any]
    ) -> Solution:
        config = self._config
        max_rounds = config.max_tool_rounds if config else 5
        tools = self._tool_registry.all()
        system_prompt = context.system_prompt_extension()

        messages: list[Message] = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=query.text),
        ]

        for _round in range(max_rounds):
            request = CompletionRequest(
                messages=messages,
                tools=(
                    [t.to_vendor_spec(self._llm_client.vendor) for t in tools] if tools else None
                ),
            )

            self._telemetry.event(
                "llm.call_started", {"round": _round, "vendor": self._llm_client.vendor}
            )
            timeout_s = (config.turn_timeout_ms if config else 60_000) / 1000
            try:
                response = await asyncio.wait_for(
                    self._llm_client.complete(request), timeout=timeout_s
                )
                self._lifecycle.record_llm_success()
            except Exception as err:
                self._lifecycle.record_llm_failure()
                self._telemetry.event(
                    "llm.call_failed",
                    {
                        "round": _round,
                        "vendor": self._llm_client.vendor,
                        "error_type": type(err).__name__,
                    },
                )
                raise
            self._telemetry.event(
                "llm.call_completed",
                {
                    "round": _round,
                    "vendor": self._llm_client.vendor,
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            )

            if response.stop_reason == "tool_use" and response.tool_calls:
                messages.append(Message(role="assistant", content=response.content))
                for tool_call in response.tool_calls:
                    result = await self._execute_tool(tool_call)
                    messages.append(Message(role="tool", content=json.dumps(result)))
                continue

            return Solution(
                content=response.content,
                format=query.format or "text",
                sources=[SourceRecord(tag=p.tag, ref=p.source) for p in self._provenance.dump()],
                metadata={"extras": extras},
            )

        return Solution(
            content=f"[TokenBudgetExceeded] Truncated after {max_rounds} tool rounds.",
            format="text",
            sources=[],
        )

    async def _execute_tool(self, tool_call: ToolCall) -> Any:
        tool = self._tool_registry.get(tool_call.name)
        if tool is None:
            self._telemetry.event(
                "tool.call_failed",
                {"tool": tool_call.name, "error_type": "ToolNotFound"},
            )
            return {"error": f"Tool not found: {tool_call.name}"}
        self._telemetry.event("tool.call_started", {"tool": tool_call.name})
        timeout_s = (self._config.tool_timeout_ms if self._config else 30_000) / 1000
        try:
            result = await asyncio.wait_for(tool.execute(tool_call.args), timeout=timeout_s)
        except Exception as err:
            _logger.exception("[OOAgent] Tool execution error: %s", tool_call.name)
            self._telemetry.event(
                "tool.call_failed",
                {"tool": tool_call.name, "error_type": type(err).__name__},
            )
            return {"error": str(err)}
        self._telemetry.event("tool.call_completed", {"tool": tool_call.name})
        return result

    def _handle_failure(
        self, err: Exception, context: IDomainContext | None, _snapshot_id: str
    ) -> Artifact:
        context_name = context.name if context is not None else "unknown"
        self._state.transition("FAILURE")
        self._telemetry.event(
            "turn.failed",
            {
                "context": context_name,
                "error_type": type(err).__name__,
                "recoverable": True,
            },
        )
        if isinstance(err, ScopeExitError):
            artifact = self._artifact_factory.build_scope_exit(context_name, err.query)
        elif isinstance(err, ConstraintViolationError):
            artifact = self._artifact_factory.build_error(str(err), context_name)
        else:
            artifact = self._artifact_factory.build_error(str(err), context_name)
        self._state.transition("DELIVERING")
        self._state.reset()
        return artifact

    def _handle_unrecoverable_failure(
        self, err: Exception, context: IDomainContext | None
    ) -> Artifact:
        """Recovers from a failure in the DELIVERING block, where `_handle_failure`'s
        `transition("FAILURE")` would be illegal — `VALID_TRANSITIONS["DELIVERING"]
        = {"IDLE"}` in state.py is the only legal exit from DELIVERING. Uses
        `reset()` to force-assign `_fsm = IDLE` unconditionally, bypassing the
        transition-legality check."""
        context_name = context.name if context is not None else "unknown"
        self._telemetry.event(
            "turn.failed",
            {"context": context_name, "error_type": type(err).__name__, "recoverable": False},
        )
        if isinstance(err, ScopeExitError):
            artifact = self._artifact_factory.build_scope_exit(context_name, err.query)
        else:
            artifact = self._artifact_factory.build_error(str(err), context_name)
        self._state.reset()
        self._lifecycle.record_llm_failure()
        return artifact
