"""Offline test doubles (no LLM, no network). Shared by the trace-seam and worker tests.

There is no production fake LLM (the engine always calls a real provider — see llm/client.py), so
tests that need to exercise the LLM phases inject a scripted ``FakeLLM`` and build the
``Investigation`` directly, bypassing ``Investigation.start`` (which would construct a real client).
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from biggy.engine.config import RunConfig
from biggy.engine.context import Investigation
from biggy.engine.evidence.tools import make_tools
from biggy.engine.evidence.vault import Vault
from biggy.engine.ledger import Ledger
from biggy.engine.schemas import Hypothesis
from biggy.engine.trace import Tracer


class CapturingSink:
    """A ``TraceSink`` that records every ``(type, data)`` for assertions."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        self.events.append((event_type, data))

    @property
    def types(self) -> list[str]:
        return [t for t, _ in self.events]


class _FakeRunnable:
    """Returns scripted outputs in order (repeats the last once exhausted)."""

    def __init__(self, outputs: list[Any]) -> None:
        self._outputs = outputs
        self._i = 0

    def invoke(self, _messages: Any) -> Any:
        out = self._outputs[min(self._i, len(self._outputs) - 1)]
        self._i += 1
        return out


class FakeLLM:
    """Scripted stand-in for ``LLMClient``: a fixed tool-loop sequence + a structured verdict."""

    def __init__(self, tool_loop: list[Any], verdict: Any) -> None:
        self._tool_loop = tool_loop
        self._verdict = verdict

    def bind_tools(self, _tools: Any) -> _FakeRunnable:
        return _FakeRunnable(self._tool_loop)

    def structured(self, _schema: Any) -> _FakeRunnable:
        return _FakeRunnable([self._verdict])


def tool_call_message(
    name: str, args: dict | None = None, call_id: str = "c1"
) -> AIMessage:
    """An assistant turn that calls one tool (drives one iteration of the test loop)."""
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args or {}, "id": call_id}]
    )


def stop_message() -> AIMessage:
    """An assistant turn with no tool calls (ends the test loop)."""
    return AIMessage(content="done")


def build_investigation(
    config: RunConfig,
    *,
    llm: Any,
    sink: CapturingSink,
    hypotheses: list[Hypothesis],
    cancel_check: Any = None,
) -> Investigation:
    """Construct an ``Investigation`` with a fake LLM (bypasses ``start``/``get_client``) for
    offline phase tests over the real Scenario-A vault."""
    vault = Vault.load(config)
    ledger = Ledger(
        incident_id="test",
        workspace=config.workspace,
        scenario="A",
        query=config.query,
    )
    ledger.initial_hypotheses = hypotheses
    return Investigation(
        config=config,
        vault=vault,
        llm=llm,
        tracer=Tracer(sink=sink),
        ledger=ledger,
        tools=make_tools(vault),
        cancel_check=cancel_check,
    )
