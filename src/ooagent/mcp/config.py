"""ooagent/mcp/config.py — environment-variable to OOAgent construction.

Information Expert on env -> object construction, mirroring how each
adapters/llm/*.py file owns its own *Config dataclass (CLAUDE.md §3).
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from ooagent.adapters.llm.anthropic import AnthropicConfig, AnthropicLLMClient
from ooagent.adapters.llm.gemini import GeminiConfig, GeminiLLMClient
from ooagent.adapters.llm.ollama import OllamaConfig, OllamaLLMClient
from ooagent.adapters.llm.openai import OpenAIConfig, OpenAILLMClient
from ooagent.contexts.null_context import NullContext
from ooagent.core.agent import OOAgent
from ooagent.core.protocols import IDomainContext, ILLMClient
from ooagent.core.registry import ContextRegistry

_VENDOR_ENV_VAR = "OOAGENT_LLM_VENDOR"
_SUPPORTED_VENDORS = ("anthropic", "openai", "gemini", "ollama")
_API_KEY_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


class ConfigError(Exception):
    """Raised when environment configuration is missing or invalid."""


def build_llm_client(env: Mapping[str, str] | None = None) -> ILLMClient:
    env = env if env is not None else os.environ
    vendor = env.get(_VENDOR_ENV_VAR)
    if not vendor:
        raise ConfigError(
            f"{_VENDOR_ENV_VAR} is not set. Set it to one of: "
            f"{', '.join(_SUPPORTED_VENDORS)}."
        )
    if vendor not in _SUPPORTED_VENDORS:
        raise ConfigError(
            f"{_VENDOR_ENV_VAR}={vendor!r} is not supported. Choose one of: "
            f"{', '.join(_SUPPORTED_VENDORS)}."
        )

    if vendor == "ollama":
        return OllamaLLMClient(OllamaConfig())

    api_key_var = _API_KEY_ENV_VARS[vendor]
    api_key = env.get(api_key_var)
    if not api_key:
        raise ConfigError(
            f"{api_key_var} is not set (required for {_VENDOR_ENV_VAR}={vendor})."
        )

    if vendor == "anthropic":
        return AnthropicLLMClient(AnthropicConfig(api_key=api_key))
    if vendor == "openai":
        return OpenAILLMClient(OpenAIConfig(api_key=api_key))
    return GeminiLLMClient(GeminiConfig(api_key=api_key))


def build_agent(env: Mapping[str, str] | None = None) -> tuple[OOAgent, list[IDomainContext]]:
    llm_client = build_llm_client(env)
    ctx_registry = ContextRegistry()
    null_context = NullContext()
    ctx_registry.register(null_context)
    agent = OOAgent(llm_client=llm_client, ctx_registry=ctx_registry)
    return agent, [null_context]
