"""core/protocols.py — all interface + type definitions (zero runtime dependencies)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Generic, Literal, Protocol, TypeVar

# ── Primitive enumerations ───────────────────────────────────────────────────

SourceTag = Literal["measured", "assumed", "cited", "derived"]

LLMVendor = Literal["anthropic", "openai", "gemini", "ollama"]

AgentFSMState = Literal[
    "IDLE",
    "GATHERING",
    "AWAITING",
    "MODELING",
    "SOLVING",
    "VALIDATING",
    "DELIVERING",
    "FAILURE",
    "DEGRADED",
]

ArtifactFormat = Literal["py", "ts", "md", "json", "sql", "html", "yaml", "mermaid", "text"]

# ── Vocabulary & domain value objects ────────────────────────────────────────


@dataclass(frozen=True)
class Term:
    label: str
    definition: str
    canonical: bool


@dataclass(frozen=True)
class ProblemClass:
    name: str
    description: str
    solver: str


@dataclass(frozen=True)
class Invariant:
    name: str
    condition: str
    severity: Literal["error", "warning"]
    rationale: str


@dataclass(frozen=True)
class AntiPattern:
    name: str
    pattern: str
    reason: str


@dataclass(frozen=True)
class InputSpec:
    name: str
    type: str
    required: bool
    description: str


@dataclass(frozen=True)
class ArtifactPolicy:
    preferred_formats: list[ArtifactFormat]
    type_hints_required: bool
    comment_policy: Literal["none", "non-obvious", "all"]
    max_prose_words: int | None = None


# ── Pipeline ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PipelineStepResult:
    passed: bool
    extras: dict[str, Any]
    violation: str | None = None


class PipelineStep(Protocol):
    """Structural (duck-typed) — matches the TS object-literal factory `createStep()`."""

    name: str

    async def run(self, query: Query, context: IDomainContext) -> PipelineStepResult: ...


# ── LLM wire types ────────────────────────────────────────────────────────────

JSONSchema = dict[str, Any]
VendorToolSpec = dict[str, Any]


@dataclass(frozen=True)
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class CompletionRequest:
    messages: list[Message]
    max_tokens: int | None = None
    temperature: float | None = None
    tools: list[VendorToolSpec] | None = None
    stop_sequences: list[str] | None = None


@dataclass(frozen=True)
class CompletionResponse:
    content: str
    stop_reason: Literal["end_turn", "max_tokens", "tool_use", "stop_sequence"]
    usage: TokenUsage
    tool_calls: list[ToolCall] | None = None


@dataclass(frozen=True)
class CompletionChunk:
    delta: str
    done: bool


# ── Domain query / solution / artifact types ──────────────────────────────────


@dataclass(frozen=True)
class Query:
    text: str
    format: ArtifactFormat | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class SourceRecord:
    tag: SourceTag
    ref: str


@dataclass(frozen=True)
class Solution:
    content: str
    format: ArtifactFormat
    sources: list[SourceRecord]
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ProvenanceRecord:
    source: str
    tag: SourceTag
    timestamp: float


@dataclass(frozen=True)
class Artifact:
    content: str
    format: ArtifactFormat
    provenance: list[ProvenanceRecord]
    metadata: dict[str, Any] | None = None


# ── Session state types ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class FSMTraceEntry:
    state: AgentFSMState
    timestamp: float


FSMTrace = list[FSMTraceEntry]
StateObserver = Callable[[AgentFSMState], None]
Unsubscribe = Callable[[], None]


@dataclass(frozen=True)
class Memento:
    id: str
    fsm: AgentFSMState
    turn: int
    context_name: str
    scratch: dict[str, Any]
    timestamp: float


@dataclass(frozen=True)
class Command:
    id: str
    query: Query
    solution: Solution
    context_name: str
    trace: FSMTrace
    timestamp: float


# ── Configuration ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentConfig:
    """Named `AgentConfig` (no `I` prefix) — a data struct, not a behavior
    contract, and not part of the §5 CLAUDE.md interface catalog."""

    max_retries: int = 3
    max_tool_rounds: int = 5
    turn_timeout_ms: int = 60_000
    tool_timeout_ms: int = 30_000
    specialist_timeout_ms: int = 30_000
    orchestration_timeout_ms: int = 120_000
    context_resolution_threshold: float = 0.1
    max_memento_entries: int = 100
    circuit_breaker_threshold: int = 5
    agent_id: str | None = None
    log_level: Literal["debug", "info", "warn", "error"] | None = "info"


DEFAULT_AGENT_CONFIG = AgentConfig()

# ── Plugin contributions ───────────────────────────────────────────────────────

ResponseDecoratorFn = Callable[["Artifact", list[ProvenanceRecord]], "Artifact"]


@dataclass(frozen=True)
class PluginContributions:
    tools: list[ITool] | None = None
    contexts: list[IDomainContext] | None = None
    solvers: list[ISolver] | None = None
    decorators: list[ResponseDecoratorFn] | None = None


# ── Health ────────────────────────────────────────────────────────────────────

HealthStatus = Literal["healthy", "degraded", "unhealthy"]

# ── Artifact tree (Composite pattern) ─────────────────────────────────────────

T = TypeVar("T")


class IVisitor(ABC, Generic[T]):
    @abstractmethod
    def visit(self, node: IArtifactNode) -> T: ...


class IArtifactNode(ABC):
    @abstractmethod
    def accept(self, visitor: IVisitor[T]) -> T: ...

    @abstractmethod
    def children(self) -> list[IArtifactNode]: ...


class IPrototypable(ABC, Generic[T]):
    @abstractmethod
    def clone(self) -> T: ...


# ── Error types ───────────────────────────────────────────────────────────────


class OOAgentError(Exception):
    """Common base for every OOAgent exception — organizational only, no TS
    equivalent (the TS version had no shared base class)."""


class ConstraintViolationError(OOAgentError):
    def __init__(self, invariant_name: str, offending_value: Any, inputs: dict[str, Any]) -> None:
        super().__init__(f"Invariant violated: {invariant_name}")
        self.invariant_name = invariant_name
        self.offending_value = offending_value
        self.inputs = inputs


class FSMViolationError(OOAgentError):
    def __init__(self, from_state: AgentFSMState, to_state: AgentFSMState, trace: FSMTrace) -> None:
        super().__init__(f"Illegal FSM transition: {from_state} → {to_state}")
        self.from_state = from_state
        self.to_state = to_state
        self.trace = trace


class LifecycleError(OOAgentError):
    pass


class ToolExecutionError(OOAgentError):
    def __init__(self, tool_name: str, args: dict[str, Any], cause: BaseException | str) -> None:
        cause_message = str(cause)
        super().__init__(f"Tool execution failed: {tool_name} — {cause_message}")
        self.tool_name = tool_name
        # Named `call_args`, not `args` — assigning a dict to `self.args` would
        # clobber `BaseException.args` (coerced via PySequence_Tuple, iterating
        # the dict's keys), silently breaking `str(err)`/`repr(err)`.
        self.call_args = args
        self.cause = cause


class TokenLimitError(OOAgentError):
    def __init__(self, requested: int, limit: int) -> None:
        super().__init__(f"Token limit exceeded: requested {requested}, limit {limit}")
        self.requested = requested
        self.limit = limit


class ScopeExitError(OOAgentError):
    def __init__(self, context: str, query: str) -> None:
        super().__init__(f"Query out of scope for context: {context}")
        self.context = context
        self.query = query


# ── Core interfaces ───────────────────────────────────────────────────────────

TQuery = TypeVar("TQuery")
TResponse = TypeVar("TResponse")


class IAgent(ABC, Generic[TQuery, TResponse]):
    @abstractmethod
    async def respond(self, query: TQuery) -> TResponse: ...

    @property
    @abstractmethod
    def agent_id(self) -> str: ...

    @property
    @abstractmethod
    def state(self) -> ISessionState: ...


class ILLMClient(ABC):
    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse: ...

    @abstractmethod
    def stream(self, request: CompletionRequest) -> AsyncIterator[CompletionChunk]: ...

    @property
    @abstractmethod
    def model_id(self) -> str: ...

    @property
    @abstractmethod
    def vendor(self) -> LLMVendor: ...

    @property
    @abstractmethod
    def max_tokens(self) -> int: ...

    @property
    @abstractmethod
    def supports_tools(self) -> bool: ...


class IDomainContext(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @abstractmethod
    def vocabulary(self) -> set[Term]: ...

    @abstractmethod
    def problem_classes(self) -> set[ProblemClass]: ...

    @abstractmethod
    def solvers(self) -> dict[str, ISolver]: ...

    @abstractmethod
    def invariants(self) -> list[Invariant]: ...

    @abstractmethod
    def pipeline(self) -> list[PipelineStep]: ...

    @abstractmethod
    def anti_patterns(self) -> list[AntiPattern]: ...

    @abstractmethod
    def required_inputs(self, pc: ProblemClass) -> list[InputSpec]: ...

    @abstractmethod
    def artifact_preferences(self) -> ArtifactPolicy: ...

    @abstractmethod
    def system_prompt_extension(self) -> str: ...

    @abstractmethod
    def resolve_intent(self, query: Query) -> ProblemClass | None: ...


class ISolver(ABC):
    @abstractmethod
    def can_solve(self, problem_class: str) -> bool: ...

    @abstractmethod
    async def solve(self, query: Query, ctx: IDomainContext) -> Solution: ...


class ITool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    def input_schema(self) -> JSONSchema: ...

    @abstractmethod
    async def execute(self, args: dict[str, Any]) -> Any: ...

    @abstractmethod
    def to_vendor_spec(self, vendor: LLMVendor) -> VendorToolSpec: ...


class IPlugin(ABC):
    @property
    @abstractmethod
    def plugin_id(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    @abstractmethod
    def on_register(self, agent: IAgent[Any, Any]) -> None: ...

    @abstractmethod
    def on_dispose(self) -> None: ...

    @abstractmethod
    def contributes(self) -> PluginContributions: ...


class ILifecycle(ABC):
    @abstractmethod
    async def initialize(self, config: AgentConfig) -> None: ...

    @abstractmethod
    async def health_check(self) -> HealthStatus: ...

    @abstractmethod
    async def dispose(self) -> None: ...

    @property
    @abstractmethod
    def is_ready(self) -> bool: ...


class ISessionState(ABC):
    @property
    @abstractmethod
    def fsm(self) -> AgentFSMState: ...

    @property
    @abstractmethod
    def turn(self) -> int: ...

    @property
    @abstractmethod
    def context_name(self) -> str: ...

    @property
    @abstractmethod
    def trace(self) -> FSMTrace: ...

    @abstractmethod
    def transition(self, to: AgentFSMState) -> None: ...

    @abstractmethod
    def set_context(self, name: str) -> None: ...

    @abstractmethod
    def snapshot(self) -> Memento: ...

    @abstractmethod
    def restore(self, id: str) -> None: ...

    @abstractmethod
    def commit(self, cmd: Command) -> None: ...

    @abstractmethod
    def subscribe(self, obs: StateObserver) -> Unsubscribe: ...

    @abstractmethod
    async def flush(self) -> None: ...

    @abstractmethod
    def reset(self) -> None: ...


class ITelemetryProvider(ABC):
    @abstractmethod
    async def span(self, name: str, fn: Callable[[], Awaitable[T]]) -> T: ...

    @abstractmethod
    def counter(self, name: str, delta: float = 1) -> None: ...

    @abstractmethod
    def gauge(self, name: str, value: float) -> None: ...

    @abstractmethod
    def histogram(self, name: str, value: float) -> None: ...

    @abstractmethod
    def event(self, name: str, payload: dict[str, Any]) -> None: ...


class IArtifactFactory(ABC):
    @abstractmethod
    def build(
        self, solution: Solution, format: ArtifactFormat, policy: ArtifactPolicy
    ) -> Artifact: ...

    @abstractmethod
    def build_error(self, violation: str, ctx: str) -> Artifact: ...

    @abstractmethod
    def build_missing_inputs(self, missing: list[InputSpec], ctx: str) -> Artifact: ...

    @abstractmethod
    def build_scope_exit(self, ctx: str, query: str) -> Artifact: ...


class IOrchestrator(ABC):
    @abstractmethod
    async def dispatch(self, query: Query, contexts: list[IDomainContext]) -> list[Solution]: ...

    @abstractmethod
    async def synthesize(self, solutions: list[Solution], original: Query) -> Solution: ...


# ── Composition interfaces ─────────────────────────────────────────────────────

TContext = TypeVar("TContext")


class IContextHost(ABC, Generic[TContext]):
    @property
    @abstractmethod
    def active_context(self) -> TContext: ...


class IConversationalObject(ABC):
    @property
    @abstractmethod
    def history(self) -> list[Command]: ...


class IToolUser(ABC):
    @property
    @abstractmethod
    def tools(self) -> list[ITool]: ...


class IObservable(ABC):
    @abstractmethod
    def subscribe(self, observer: StateObserver) -> Unsubscribe: ...
