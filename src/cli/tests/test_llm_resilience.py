"""The LLM client's resilience seam: transient-error backoff + structured-output repair.

Offline — no provider, no network. A fake chat model lets us script transient failures and
schema-violating outputs and assert the client recovers (and gives up *cleanly* when it can't).
Backoff is set to zero here so retries don't actually sleep.
"""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from biggy.engine.llm.client import (
    LLMClient,
    RetryPolicy,
    StructuredOutputError,
    _is_transient,
)


class _Verdict(BaseModel):
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)


class _Boom(Exception):
    """Carries an HTTP-style status so ``_is_transient`` can classify it like a provider error."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _policy(**overrides: Any) -> RetryPolicy:
    base = dict(
        max_attempts=3,
        max_repairs=2,
        backoff_initial=0.0,
        backoff_max=0.0,
        backoff_jitter=0.0,
    )
    base.update(overrides)
    return RetryPolicy(**base)


class _ScriptedRunnable:
    """Yields scripted results/exceptions per ``.invoke``; records every payload it was handed."""

    def __init__(self, steps: list[Any]):
        self._steps = list(steps)
        self.calls: list[Any] = []
        self._i = 0

    def invoke(self, payload: Any, **_: Any) -> Any:
        self.calls.append(payload)
        step = self._steps[min(self._i, len(self._steps) - 1)]
        self._i += 1
        if isinstance(step, Exception):
            raise step
        return step


class _FakeChatModel:
    """Stands in for an ``init_chat_model`` result (injected via ``chat_model=``)."""

    def __init__(
        self,
        *,
        tool_steps: list[Any] | None = None,
        structured_steps: list[Any] | None = None,
    ):
        self.tools = _ScriptedRunnable(tool_steps or [])
        self.structured = _ScriptedRunnable(structured_steps or [])
        self.structured_kwargs: dict[str, Any] = {}

    def bind_tools(self, _tools: Any) -> _ScriptedRunnable:
        return self.tools

    def with_structured_output(self, _schema: Any, **kwargs: Any) -> _ScriptedRunnable:
        self.structured_kwargs = kwargs
        return self.structured


def _client(model: _FakeChatModel, **policy_kw: Any) -> LLMClient:
    return LLMClient("fake", "fake", policy=_policy(**policy_kw), chat_model=model)


# --- transient classification -------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc",
    [
        _Boom("rate limited", 429),
        _Boom("service unavailable", 503),
        _Boom("502 bad gateway", 502),
        _Boom("the model is overloaded, please try again"),
        _Boom("resource exhausted: quota exceeded"),
        TimeoutError("deadline exceeded"),
    ],
)
def test_transient_errors_are_retryable(exc: Exception) -> None:
    assert _is_transient(exc) is True


@pytest.mark.parametrize(
    "exc",
    [
        _Boom("bad request", 400),
        _Boom("unauthorized", 401),
        _Boom("forbidden", 403),
        ValueError("schema is wrong"),
        KeyError("missing field"),
    ],
)
def test_fatal_errors_are_not_retryable(exc: Exception) -> None:
    assert _is_transient(exc) is False


# --- tool loop (bind_tools) ---------------------------------------------------------------------


def test_bind_tools_retries_transient_then_succeeds() -> None:
    ok = AIMessage(content="done")
    model = _FakeChatModel(tool_steps=[_Boom("429 rate limit", 429), ok])
    out = _client(model).bind_tools([]).invoke([HumanMessage(content="go")])
    assert out is ok
    assert len(model.tools.calls) == 2  # one failure, one success


def test_bind_tools_reraises_after_exhausting_attempts() -> None:
    model = _FakeChatModel(tool_steps=[_Boom("503 unavailable", 503)])
    with pytest.raises(_Boom):
        _client(model, max_attempts=3).bind_tools([]).invoke(
            [HumanMessage(content="go")]
        )
    assert len(model.tools.calls) == 3  # all attempts used


def test_bind_tools_does_not_retry_fatal_errors() -> None:
    model = _FakeChatModel(tool_steps=[_Boom("400 bad request", 400)])
    with pytest.raises(_Boom):
        _client(model, max_attempts=3).bind_tools([]).invoke(
            [HumanMessage(content="go")]
        )
    assert len(model.tools.calls) == 1  # failed fast, no retry


# --- structured output (repair) -----------------------------------------------------------------


def _raw(text: str) -> AIMessage:
    return AIMessage(content=text)


def test_structured_output_repairs_then_succeeds() -> None:
    bad = {
        "raw": _raw("{confidence: 2.0}"),
        "parsed": None,
        "parsing_error": ValueError("confidence must be <= 1"),
    }
    good = {
        "raw": _raw("ok"),
        "parsed": _Verdict(answer="redis pool exhaustion", confidence=0.9),
        "parsing_error": None,
    }
    model = _FakeChatModel(structured_steps=[bad, good])

    out = (
        _client(model).structured(_Verdict).invoke([HumanMessage(content="adjudicate")])
    )

    assert isinstance(out, _Verdict) and out.answer == "redis pool exhaustion"
    assert (
        model.structured_kwargs.get("include_raw") is True
    )  # repair needs the raw output
    # The repair round fed the error back, so the second call's conversation is longer.
    assert len(model.structured.calls) == 2
    assert len(model.structured.calls[1]) > len(model.structured.calls[0])


def test_structured_output_raises_after_repair_budget() -> None:
    bad = {
        "raw": _raw("nope"),
        "parsed": None,
        "parsing_error": ValueError("still wrong"),
    }
    model = _FakeChatModel(structured_steps=[bad])  # never recovers
    with pytest.raises(StructuredOutputError) as ei:
        _client(model, max_repairs=2).structured(_Verdict).invoke(
            [HumanMessage(content="adjudicate")]
        )
    assert ei.value.schema_name == "_Verdict"
    assert len(model.structured.calls) == 3  # 1 initial + 2 repairs


def test_structured_output_validates_dict_parsed() -> None:
    good = {
        "raw": _raw("{}"),
        "parsed": {"answer": "x", "confidence": 0.5},  # parser handed back a dict
        "parsing_error": None,
    }
    model = _FakeChatModel(structured_steps=[good])
    out = _client(model).structured(_Verdict).invoke([HumanMessage(content="go")])
    assert isinstance(out, _Verdict) and out.confidence == 0.5


def test_structured_output_retries_transient_within_a_round() -> None:
    good = {
        "raw": _raw("{}"),
        "parsed": _Verdict(answer="x", confidence=0.5),
        "parsing_error": None,
    }
    model = _FakeChatModel(structured_steps=[_Boom("429", 429), good])
    out = _client(model).structured(_Verdict).invoke([HumanMessage(content="go")])
    assert isinstance(out, _Verdict)
    assert len(model.structured.calls) == 2  # transient retry, not a repair round
