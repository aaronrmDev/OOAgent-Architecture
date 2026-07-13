"""core/lifecycle.py — LifecycleManager, CircuitBreaker."""

from __future__ import annotations

import atexit
import logging
import signal

from ooagent.core.protocols import (
    AgentConfig,
    HealthStatus,
    ILifecycle,
    ILLMClient,
    LifecycleError,
)
from ooagent.core.registry import PluginRegistry
from ooagent.core.state import SessionState

_logger = logging.getLogger("ooagent.lifecycle")


class CircuitBreaker:
    """Degrades after N consecutive failures — §6 CLAUDE.md."""

    def __init__(self, threshold: int) -> None:
        self._threshold = threshold
        self._failures = 0
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open

    def record_success(self) -> None:
        self._failures = 0
        self._open = False

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold:
            self._open = True

    def reset(self) -> None:
        self._failures = 0
        self._open = False


class LifecycleManager(ILifecycle):
    def __init__(
        self,
        plugin_registry: PluginRegistry,
        state: SessionState,
        llm_client: ILLMClient | None = None,
    ) -> None:
        self._plugin_registry = plugin_registry
        self._state = state
        self._llm_client = llm_client
        self._ready = False
        self._disposed = False
        self._circuit_breaker: CircuitBreaker | None = None
        self._exit_handler_registered = False

    async def initialize(self, config: AgentConfig) -> None:
        """Ordered initialization — §6 CLAUDE.md."""
        if self._disposed:
            raise LifecycleError("Cannot initialize a disposed agent")
        if self._ready:
            return

        self._circuit_breaker = CircuitBreaker(config.circuit_breaker_threshold)
        self._plugin_registry.verify()
        self._ready = True

        if not self._exit_handler_registered:
            self._register_exit_handlers()
            self._exit_handler_registered = True

    async def health_check(self) -> HealthStatus:
        if not self._ready:
            return "unhealthy"
        if self._llm_client is not None:
            try:
                reachable = await self._llm_client.ping()
            except Exception:
                return "unhealthy"
            if not reachable:
                return "unhealthy"
        if self._circuit_breaker is not None and self._circuit_breaker.is_open:
            return "degraded"
        return "healthy"

    async def dispose(self) -> None:
        """Graceful dispose — §6 CLAUDE.md.

        Idempotent per §17 CLAUDE.md conformance contract: a second call
        (after a first successful dispose) is a no-op, not an error. This is
        distinct from disposing an agent that was NEVER initialized, which
        still raises — there is nothing to release and no successful
        initialize() ever happened.
        """
        if self._disposed:
            return
        if not self._ready:
            raise LifecycleError("Cannot dispose an uninitialized agent")
        await self._plugin_registry.dispose_all()
        await self._state.flush()
        self._ready = False
        self._disposed = True

    @property
    def is_ready(self) -> bool:
        return self._ready

    def record_llm_success(self) -> None:
        if self._circuit_breaker is not None:
            self._circuit_breaker.record_success()

    def record_llm_failure(self) -> None:
        if self._circuit_breaker is not None:
            self._circuit_breaker.record_failure()

    def _register_exit_handlers(self) -> None:
        def handler(*_args: object) -> None:
            if self._ready:
                import asyncio

                try:
                    # No running loop exists at atexit/signal time (and
                    # asyncio.get_event_loop() no longer auto-creates one
                    # outside a coroutine as of Python 3.10+), so a fresh
                    # loop is created, driven to completion, and closed.
                    loop = asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(self.dispose())
                    finally:
                        loop.close()
                except Exception:
                    _logger.exception("[LifecycleManager] Dispose error")

        atexit.register(handler)
        try:
            signal.signal(signal.SIGINT, handler)
            signal.signal(signal.SIGTERM, handler)
        except (ValueError, OSError):
            # signal() only works in the main thread — mirrors the TS guard
            # for environments where `process` (or here, signal handling) is
            # unavailable.
            pass
