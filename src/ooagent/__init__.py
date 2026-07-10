"""ooagent — Object-Oriented AI Agent Framework (backend-agnostic, domain-agnostic).

Core primitives — the surface most app teams need:

    from ooagent import OOAgent, AgentConfig, Query, Artifact

Extension-point interfaces and the two registries the golden-path
examples (examples/*.py) already touch directly:

    from ooagent import ILLMClient, IDomainContext, ITool, IPlugin
    from ooagent import ContextRegistry, ToolRegistry

The exception hierarchy, catchable without deep imports:

    from ooagent import OOAgentError, ConstraintViolationError, FSMViolationError
    from ooagent import LifecycleError, ToolExecutionError, TokenLimitError, ScopeExitError

Everything else (ArtifactFactory, ConstraintEngine, LifecycleManager,
MultiAgentOrchestrator, the advanced-only ABCs, IDeliveryWorkflow, ...) is
the "advanced" tier — reachable via `ooagent.core`, `ooagent.adapters`,
`ooagent.workflow`, etc. See docs/PUBLIC_API.md for the full split and the
stability contract (CLAUDE.md §18).
"""

from __future__ import annotations

from ooagent.core.agent import OOAgent
from ooagent.core.protocols import (
    AgentConfig,
    Artifact,
    ConstraintViolationError,
    FSMViolationError,
    IDomainContext,
    ILLMClient,
    IPlugin,
    ITool,
    LifecycleError,
    OOAgentError,
    Query,
    ScopeExitError,
    TokenLimitError,
    ToolExecutionError,
)
from ooagent.core.registry import ContextRegistry, ToolRegistry

__all__ = [
    "OOAgent",
    "AgentConfig",
    "Query",
    "Artifact",
    "ILLMClient",
    "IDomainContext",
    "ITool",
    "IPlugin",
    "ContextRegistry",
    "ToolRegistry",
    "OOAgentError",
    "ConstraintViolationError",
    "FSMViolationError",
    "LifecycleError",
    "ToolExecutionError",
    "TokenLimitError",
    "ScopeExitError",
]
