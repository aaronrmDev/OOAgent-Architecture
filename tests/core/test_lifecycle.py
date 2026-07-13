"""tests/core/test_lifecycle.py — LifecycleManager, CircuitBreaker."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from ooagent.core.lifecycle import CircuitBreaker, LifecycleManager
from ooagent.core.protocols import (
    AgentConfig,
    CompletionChunk,
    CompletionRequest,
    CompletionResponse,
    ILLMClient,
    LifecycleError,
    LLMVendor,
)
from ooagent.core.registry import PluginRegistry
from ooagent.core.state import SessionState


def test_circuit_breaker_opens_after_threshold_failures() -> None:
    breaker = CircuitBreaker(threshold=3)
    assert not breaker.is_open
    breaker.record_failure()
    breaker.record_failure()
    assert not breaker.is_open
    breaker.record_failure()
    assert breaker.is_open
    breaker.record_success()
    assert not breaker.is_open


async def test_initialize_sets_ready_and_health_check_reports_healthy() -> None:
    manager = LifecycleManager(PluginRegistry(), SessionState())
    assert not manager.is_ready
    await manager.initialize(AgentConfig())
    assert manager.is_ready
    assert await manager.health_check() == "healthy"


async def test_dispose_before_initialize_raises_lifecycle_error() -> None:
    manager = LifecycleManager(PluginRegistry(), SessionState())
    with pytest.raises(LifecycleError):
        await manager.dispose()


async def test_dispose_after_initialize_sets_not_ready() -> None:
    manager = LifecycleManager(PluginRegistry(), SessionState())
    await manager.initialize(AgentConfig())
    await manager.dispose()
    assert not manager.is_ready


async def test_initialize_after_dispose_raises_lifecycle_error() -> None:
    manager = LifecycleManager(PluginRegistry(), SessionState())
    await manager.initialize(AgentConfig())
    await manager.dispose()
    with pytest.raises(LifecycleError):
        await manager.initialize(AgentConfig())


async def test_health_check_reports_degraded_when_circuit_breaker_open() -> None:
    manager = LifecycleManager(PluginRegistry(), SessionState())
    await manager.initialize(AgentConfig(circuit_breaker_threshold=1))
    manager.record_llm_failure()
    assert await manager.health_check() == "degraded"


async def test_health_check_reports_unhealthy_when_llm_ping_fails() -> None:
    """Test that health_check returns 'unhealthy' when LLM ping fails."""

    class _UnreachableLLMClient(ILLMClient):
        async def complete(
            self, request: CompletionRequest
        ) -> CompletionResponse:
            raise NotImplementedError

        async def ping(self) -> bool:
            return False

        def stream(
            self, request: CompletionRequest
        ) -> AsyncIterator[CompletionChunk]:
            raise NotImplementedError

        @property
        def model_id(self) -> str:
            return "unreachable"

        @property
        def vendor(self) -> LLMVendor:
            return "anthropic"

        @property
        def max_tokens(self) -> int:
            return 1

        @property
        def supports_tools(self) -> bool:
            return False

    manager = LifecycleManager(
        PluginRegistry(), SessionState(), llm_client=_UnreachableLLMClient()
    )
    await manager.initialize(AgentConfig())
    assert await manager.health_check() == "unhealthy"
