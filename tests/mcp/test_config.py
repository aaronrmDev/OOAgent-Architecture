"""tests/mcp/test_config.py — env-var to OOAgent construction."""

from __future__ import annotations

import pytest

from ooagent.adapters.llm.anthropic import AnthropicLLMClient
from ooagent.adapters.llm.gemini import GeminiLLMClient
from ooagent.adapters.llm.ollama import OllamaLLMClient
from ooagent.adapters.llm.openai import OpenAILLMClient
from ooagent.contexts.null_context import NullContext
from ooagent.core.agent import OOAgent
from ooagent.mcp.config import ConfigError, build_agent, build_llm_client


def test_build_llm_client_anthropic() -> None:
    client = build_llm_client({"OOAGENT_LLM_VENDOR": "anthropic", "ANTHROPIC_API_KEY": "key-1"})
    assert isinstance(client, AnthropicLLMClient)
    assert client._api_key == "key-1"


def test_build_llm_client_openai() -> None:
    client = build_llm_client({"OOAGENT_LLM_VENDOR": "openai", "OPENAI_API_KEY": "key-2"})
    assert isinstance(client, OpenAILLMClient)
    assert client._api_key == "key-2"


def test_build_llm_client_gemini() -> None:
    client = build_llm_client({"OOAGENT_LLM_VENDOR": "gemini", "GEMINI_API_KEY": "key-3"})
    assert isinstance(client, GeminiLLMClient)
    assert client._api_key == "key-3"


def test_build_llm_client_ollama_needs_no_api_key() -> None:
    client = build_llm_client({"OOAGENT_LLM_VENDOR": "ollama"})
    assert isinstance(client, OllamaLLMClient)
    assert hasattr(client, "_model_id")


def test_build_llm_client_missing_vendor_raises() -> None:
    with pytest.raises(ConfigError, match="OOAGENT_LLM_VENDOR"):
        build_llm_client({})


def test_build_llm_client_unsupported_vendor_raises() -> None:
    with pytest.raises(ConfigError, match="not supported"):
        build_llm_client({"OOAGENT_LLM_VENDOR": "not-a-real-vendor"})


def test_build_llm_client_anthropic_missing_key_raises() -> None:
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        build_llm_client({"OOAGENT_LLM_VENDOR": "anthropic"})


def test_build_agent_returns_agent_and_null_context() -> None:
    agent, contexts = build_agent({"OOAGENT_LLM_VENDOR": "ollama"})
    assert isinstance(agent, OOAgent)
    assert len(contexts) == 1
    assert isinstance(contexts[0], NullContext)
