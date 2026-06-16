"""P1 — the engine trace seam (docs/PHASE2.md §5/§7).

Drives the LLM phases offline with a scripted ``FakeLLM`` and asserts the engine emits the full
event vocabulary the worker fans out — including the P1 additions ``tool_result`` + ``verdict`` —
and that a cancel signal aborts the loop *between* steps. No network / no LLM.
"""

from __future__ import annotations

import pytest
from _fakes import (
    CapturingSink,
    FakeLLM,
    build_investigation,
    stop_message,
    tool_call_message,
)

from biggy.engine.context import InvestigationCancelled
from biggy.engine.phases import Adjudicate, Investigate, Verify
from biggy.engine.schemas import EvidenceRef, Hypothesis, InvestigationResult


def _hypotheses() -> list[Hypothesis]:
    return [
        Hypothesis(
            id="H1",
            statement="the rate-limiter change exhausted the shared pool",
            service="rate-limiter",
            confidence=0.4,
            disconfirming_test="check whether DB latency moved with the symptom onset",
        )
    ]


def _verdict(query: str) -> InvestigationResult:
    return InvestigationResult(
        query=query,
        outcome="root_cause",
        summary="the rate-limiter config change exhausted the shared Redis pool",
        hypotheses=[
            Hypothesis(
                id="H1",
                statement="rate-limiter config change exhausted the pool",
                service="rate-limiter",
                confidence=0.8,
                status="confirmed",
                supporting=[
                    EvidenceRef(
                        claim="max_tokens was cut 100 -> 10",
                        snippet="max_tokens: 10",
                        source="telemetry/changes/dep-7e2a.diff:9",
                    )
                ],
            )
        ],
        recommended_action="roll back dep-7e2a",
    )


def test_seam_emits_tool_result_verdict_and_grounding(config_a) -> None:
    sink = CapturingSink()
    llm = FakeLLM(
        tool_loop=[tool_call_message("list_evidence"), stop_message()],
        verdict=_verdict(config_a.query),
    )
    inv = build_investigation(config_a, llm=llm, sink=sink, hypotheses=_hypotheses())

    Investigate().run(inv)
    Adjudicate().run(inv)
    Verify().run(inv)

    types = sink.types
    assert "tool_call" in types
    assert "tool_result" in types  # P1 addition
    assert "thinking_done" in types
    assert "verdict" in types  # P1 addition
    assert "grounding" in types
    # a step's tool_result follows its tool_call; grounding follows the verdict
    assert types.index("tool_call") < types.index("tool_result")
    assert types.index("verdict") < types.index("grounding")


def test_cancel_aborts_between_steps(config_a) -> None:
    sink = CapturingSink()
    llm = FakeLLM(
        tool_loop=[tool_call_message("list_evidence"), stop_message()],
        verdict=_verdict(config_a.query),
    )
    inv = build_investigation(
        config_a,
        llm=llm,
        sink=sink,
        hypotheses=_hypotheses(),
        cancel_check=lambda: True,
    )

    with pytest.raises(InvestigationCancelled):
        Investigate().run(inv)
    assert "tool_call" not in sink.types  # cancelled before the first step ran
