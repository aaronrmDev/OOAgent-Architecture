"""tests/core/test_protocols.py — sanity checks for core/protocols.py."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from ooagent.core.protocols import (
    AgentConfig,
    Article,
    GateResult,
    GateSpec,
    IAgent,
    IDeliveryWorkflow,
    ILLMClient,
    Invariant,
    Phase,
    Query,
    Solution,
    ToolExecutionError,
    TraceabilityEntry,
)


def test_agent_config_has_expected_defaults() -> None:
    config = AgentConfig()
    assert config.max_retries == 3
    assert config.max_tool_rounds == 5
    assert config.circuit_breaker_threshold == 5


def test_query_is_a_frozen_dataclass() -> None:
    q = Query(text="hello")
    with pytest.raises(FrozenInstanceError):
        q.text = "changed"  # type: ignore[misc]


def test_iagent_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        IAgent()  # type: ignore[abstract]


def test_illmclient_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        ILLMClient()  # type: ignore[abstract]


def test_tool_execution_error_preserves_message_and_call_args() -> None:
    err = ToolExecutionError("calculator", {"expression": "1+1"}, ValueError("boom"))
    assert "Tool execution failed: calculator" in str(err)
    assert err.call_args == {"expression": "1+1"}
    assert err.tool_name == "calculator"


def test_idelivery_workflow_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        IDeliveryWorkflow()  # type: ignore[abstract]


def test_phase_is_a_frozen_dataclass() -> None:
    p = Phase(
        name="/specify",
        artifact="spec.md",
        itil_stage="Engage",
        cobit_domain="APO",
        owasp_gate="abuse-cases noted",
        oop_pattern="-",
    )
    with pytest.raises(FrozenInstanceError):
        p.name = "changed"  # type: ignore[misc]


def test_article_is_a_frozen_dataclass() -> None:
    a = Article(numeral="I", title="Form", body="...", key="form")
    with pytest.raises(FrozenInstanceError):
        a.title = "changed"  # type: ignore[misc]


def test_gate_spec_is_a_frozen_dataclass() -> None:
    g = GateSpec(name="lint", required=True, intent="linter, zero warnings")
    with pytest.raises(FrozenInstanceError):
        g.required = False  # type: ignore[misc]


def test_traceability_entry_allows_none_for_unresolved_fields() -> None:
    entry = TraceabilityEntry(
        req_id="REQ-1",
        ac_id="AC-1",
        task_id=None,
        test_id=None,
        code_ref=None,
        ci_evidence=None,
    )
    assert entry.task_id is None
    assert entry.test_id is None


def test_gate_result_is_a_frozen_dataclass() -> None:
    r = GateResult(gate_name="verify-spec", passed=True, message="ok")
    with pytest.raises(FrozenInstanceError):
        r.passed = False  # type: ignore[misc]


def test_invariant_check_field_defaults_to_none_and_accepts_a_callable() -> None:
    bare = Invariant(name="n", condition="c", severity="error", rationale="r")
    assert bare.check is None

    def _always_true(solution: Solution) -> bool:
        return True

    checked = Invariant(
        name="n2",
        condition="c2",
        severity="error",
        rationale="r2",
        check=_always_true,
    )
    assert checked.check is not None
    assert checked.check(Solution(content="x", format="text", sources=[])) is True
