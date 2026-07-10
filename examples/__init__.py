"""examples/__init__.py — runnable golden-path examples for OOAgent.

Each example is a complete, self-contained script demonstrating one tier
of the framework's onboarding path. Run any of them directly:

    uv run python -m examples.minimal_agent
    uv run python -m examples.tool_enabled_agent
    uv run python -m examples.domain_context_agent
    uv run python -m examples.telemetry_enabled_agent

None of these require an API key — they use DemoLLMClient
(examples/_common.py), a deterministic ILLMClient. Swap it for
ooagent.adapters.llm.anthropic.AnthropicLLMClient (or any other
ILLMClient) to talk to a real provider.
"""

from __future__ import annotations
