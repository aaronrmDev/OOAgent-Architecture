"""ooagent.core — barrel export for the core package."""

from ooagent.core.agent import AbstractAgent, LLMAgent, OOAgent  # noqa: F401 - re-export
from ooagent.core.artifacts import (  # noqa: F401 - re-export
    ArtifactFactory,
    ProvenanceTracker,
    ResponseDecorator,
)
from ooagent.core.lifecycle import CircuitBreaker, LifecycleManager  # noqa: F401 - re-export
from ooagent.core.orchestrator import MultiAgentOrchestrator, SignalBus  # noqa: F401 - re-export
from ooagent.core.pipeline import (  # noqa: F401 - re-export
    ConstraintEngine,
    ResponsePipeline,
    create_step,
)
from ooagent.core.protocols import *  # noqa: F403 - re-export every protocol/type/exception
from ooagent.core.registry import (  # noqa: F401 - re-export
    ContextRegistry,
    PluginRegistry,
    ToolRegistry,
)
from ooagent.core.state import SessionState  # noqa: F401 - re-export
