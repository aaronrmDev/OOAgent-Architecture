"""tests/test_public_api.py — the top-level ooagent import surface (docs/PUBLIC_API.md)."""

from __future__ import annotations

import ooagent
from ooagent.core.agent import OOAgent as _OOAgent
from ooagent.core.protocols import AgentConfig as _AgentConfig
from ooagent.core.protocols import Artifact as _Artifact
from ooagent.core.protocols import ConstraintViolationError as _ConstraintViolationError
from ooagent.core.protocols import FSMViolationError as _FSMViolationError
from ooagent.core.protocols import IDomainContext as _IDomainContext
from ooagent.core.protocols import ILLMClient as _ILLMClient
from ooagent.core.protocols import IPlugin as _IPlugin
from ooagent.core.protocols import ITool as _ITool
from ooagent.core.protocols import LifecycleError as _LifecycleError
from ooagent.core.protocols import OOAgentError as _OOAgentError
from ooagent.core.protocols import Query as _Query
from ooagent.core.protocols import ScopeExitError as _ScopeExitError
from ooagent.core.protocols import TokenLimitError as _TokenLimitError
from ooagent.core.protocols import ToolExecutionError as _ToolExecutionError
from ooagent.core.registry import ContextRegistry as _ContextRegistry
from ooagent.core.registry import ToolRegistry as _ToolRegistry


def test_ooagent_is_the_same_object_as_core_agent_ooagent() -> None:
    assert ooagent.OOAgent is _OOAgent


def test_agent_config_is_the_same_object_as_core_protocols_agent_config() -> None:
    assert ooagent.AgentConfig is _AgentConfig


def test_query_is_the_same_object_as_core_protocols_query() -> None:
    assert ooagent.Query is _Query


def test_artifact_is_the_same_object_as_core_protocols_artifact() -> None:
    assert ooagent.Artifact is _Artifact


def test_illmclient_is_the_same_object_as_core_protocols_illmclient() -> None:
    assert ooagent.ILLMClient is _ILLMClient


def test_idomaincontext_is_the_same_object_as_core_protocols_idomaincontext() -> None:
    assert ooagent.IDomainContext is _IDomainContext


def test_itool_is_the_same_object_as_core_protocols_itool() -> None:
    assert ooagent.ITool is _ITool


def test_iplugin_is_the_same_object_as_core_protocols_iplugin() -> None:
    assert ooagent.IPlugin is _IPlugin


def test_context_registry_is_the_same_object_as_core_registry_context_registry() -> None:
    assert ooagent.ContextRegistry is _ContextRegistry


def test_tool_registry_is_the_same_object_as_core_registry_tool_registry() -> None:
    assert ooagent.ToolRegistry is _ToolRegistry


def test_ooagent_error_is_the_same_object_as_core_protocols_ooagent_error() -> None:
    assert ooagent.OOAgentError is _OOAgentError


def test_constraint_violation_error_is_the_same_object_as_core_protocols_version() -> None:
    assert ooagent.ConstraintViolationError is _ConstraintViolationError


def test_fsm_violation_error_is_the_same_object_as_core_protocols_version() -> None:
    assert ooagent.FSMViolationError is _FSMViolationError


def test_lifecycle_error_is_the_same_object_as_core_protocols_version() -> None:
    assert ooagent.LifecycleError is _LifecycleError


def test_tool_execution_error_is_the_same_object_as_core_protocols_version() -> None:
    assert ooagent.ToolExecutionError is _ToolExecutionError


def test_token_limit_error_is_the_same_object_as_core_protocols_version() -> None:
    assert ooagent.TokenLimitError is _TokenLimitError


def test_scope_exit_error_is_the_same_object_as_core_protocols_version() -> None:
    assert ooagent.ScopeExitError is _ScopeExitError


def test_all_exports_exactly_match_the_dunder_all_list() -> None:
    expected = {
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
    }
    assert set(ooagent.__all__) == expected
