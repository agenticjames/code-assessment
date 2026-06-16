"""Provider-abstracted chat client (LangChain ``init_chat_model``) with a resilience seam.

The engine talks to this wrapper, never to a provider SDK — so swapping providers is a
``--provider/--model`` change. Two methods mirror the two LLM uses in the engine:
``bind_tools`` (the tool loop) and ``structured`` (the final typed verdict). Every run makes
real LLM calls; there is no offline stub.

Both surfaces are wrapped in two layers of recovery so one hiccup doesn't sink an investigation:

1. **Transient-error backoff** — a 429/503/timeout on any single call is retried with
   exponential backoff + jitter (``tenacity``), classified by a provider-agnostic predicate so
   we never import a vendor SDK to know what's retryable.
2. **Structured-output repair** — a schema-violating verdict is fed back to the model with the
   validation error so it can correct itself, bounded by a repair budget. At temperature 0 a
   blind retry would reproduce the same bad output, so the *correction message* is what makes
   the next attempt different.

Both budgets are bounded: once exhausted, the original error surfaces (the worker turns it into a
clean failed run — see ``worker/runner.py``). Known residual gaps are named in
``docs/PHASE2.md`` (no job-level retry / dead-letter queue, no circuit breaker or provider
failover, in-process only).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)


def ensure_google_key() -> bool:
    """``google_genai`` expects ``GOOGLE_API_KEY``; the repo's ``.env`` uses ``GEMINI_API_KEY``.

    Map one to the other if needed. Returns True if a usable key is present.
    """
    if not os.environ.get("GOOGLE_API_KEY") and os.environ.get("GEMINI_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
    return bool(os.environ.get("GOOGLE_API_KEY"))


# --- transient-error classification -------------------------------------------------------------
# Provider-agnostic on purpose: we identify retryable failures by HTTP status, exception class
# name, and message text rather than importing ``google.api_core.exceptions`` (which would break
# the "no provider SDK in the engine" rule). The cost of a false positive is a few wasted retries;
# the cost of a false negative is a failed run — so we lean inclusive but keep the budget small.

_TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}
_TRANSIENT_NAMES = (
    "resourceexhausted",
    "serviceunavailable",
    "deadlineexceeded",
    "internalservererror",
    "toomanyrequests",
    "ratelimit",
    "aborted",
    "timeout",  # TimeoutError, ReadTimeout, ConnectTimeout, APITimeoutError, ...
    "connecterror",
    "connectionerror",
    "remoteprotocolerror",
)
_TRANSIENT_MESSAGES = (
    "rate limit",
    "rate-limit",
    "resource exhausted",
    "quota exceeded",
    "overloaded",
    "unavailable",
    "deadline exceeded",
    "timed out",
    "timeout",
    "temporarily",
    "try again",
    "connection reset",
    "connection aborted",
)


def _status_code(exc: BaseException) -> int | None:
    """Best-effort HTTP status pulled off the exception without calling any methods."""
    for attr in ("status_code", "http_status", "code", "status"):
        val = getattr(exc, attr, None)
        # ``True``/``False`` are ints in Python — skip them; ``code`` is a method on gRPC errors.
        if isinstance(val, bool) or not isinstance(val, int):
            continue
        return val
    return None


def _is_transient(exc: BaseException) -> bool:
    """True for the failures worth retrying (rate limits, server errors, timeouts, conn drops)."""
    if _status_code(exc) in _TRANSIENT_STATUS:
        return True
    name = type(exc).__name__.lower()
    if any(token in name for token in _TRANSIENT_NAMES):
        return True
    text = str(exc).lower()
    return any(token in text for token in _TRANSIENT_MESSAGES)


# --- retry / repair policy ----------------------------------------------------------------------


@dataclass(frozen=True)
class RetryPolicy:
    """How hard to try before giving up. Counts are ops-tunable via env; backoff stays code-set."""

    # attempts per LLM call on transient errors (1 try + 3 retries)
    max_attempts: int = 4
    # re-prompts to fix a schema-violating structured output
    max_repairs: int = 2
    backoff_initial: float = 0.5  # seconds before the first retry
    backoff_max: float = 8.0  # ceiling on a single backoff wait
    backoff_jitter: float = 0.5  # random spread per wait, de-correlates retries

    @classmethod
    def from_env(cls) -> "RetryPolicy":
        def _int(name: str, default: int) -> int:
            try:
                return max(1, int(os.environ[name]))
            except (KeyError, ValueError):
                return default

        return cls(
            max_attempts=_int("BIGGY_LLM_MAX_ATTEMPTS", cls.max_attempts),
            max_repairs=_int("BIGGY_LLM_MAX_REPAIRS", cls.max_repairs),
        )


class StructuredOutputError(ValueError):
    """The model could not produce a schema-valid object even after the repair budget ran out."""

    def __init__(self, schema_name: str, error: BaseException | None):
        self.schema_name = schema_name
        self.error = error
        super().__init__(
            f"LLM failed to produce valid {schema_name} after repair attempts: {error}"
        )


def _make_retryer(policy: RetryPolicy, label: str) -> Retrying:
    """A tenacity loop that retries only transient errors, then re-raises the original."""
    return Retrying(
        retry=retry_if_exception(_is_transient),
        wait=wait_exponential_jitter(
            initial=policy.backoff_initial,
            max=policy.backoff_max,
            jitter=policy.backoff_jitter,
        ),
        stop=stop_after_attempt(policy.max_attempts),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,  # surface the provider error itself, not tenacity's RetryError wrapper
    )


def _as_model(parsed: Any, schema: type) -> Any:
    """Normalize a structured parse to a validated model instance (parsers may hand back a dict)."""
    if isinstance(parsed, schema):
        return parsed
    if isinstance(parsed, dict) and hasattr(schema, "model_validate"):
        return schema.model_validate(parsed)
    return parsed


# --- the wrappers the engine actually calls -----------------------------------------------------


class _RetryingRunnable:
    """Wraps a bound runnable so each ``.invoke`` retries transient provider errors.

    Used for the tool loop: a 429 on step 7 retries that one call instead of failing the run.
    The return value (an ``AIMessage`` carrying ``tool_calls``) passes straight through.
    """

    def __init__(self, runnable: Any, policy: RetryPolicy, label: str):
        self._runnable = runnable
        self._policy = policy
        self._label = label

    def invoke(self, payload: Any, **kwargs: Any) -> Any:
        return _make_retryer(self._policy, self._label)(
            self._runnable.invoke, payload, **kwargs
        )


class _StructuredCaller:
    """Runs a structured call with transient-retry *and* schema-repair.

    ``include_raw=True`` turns parse/validation failures into a ``parsing_error`` field (instead of
    an exception) so we can inspect the bad output and re-prompt with the error fed back. Each
    repair round is itself wrapped in transient-retry. After ``max_repairs`` corrections we give up
    with a ``StructuredOutputError`` that names the schema and the last validation error.
    """

    def __init__(self, model: Any, schema: type, policy: RetryPolicy):
        self._runnable = model.with_structured_output(schema, include_raw=True)
        self._schema = schema
        self._policy = policy

    def invoke(self, messages: Any, **kwargs: Any) -> Any:
        convo = list(messages)
        last_error: BaseException | None = None
        retryer = _make_retryer(self._policy, f"structured:{self._schema.__name__}")
        rounds = self._policy.max_repairs + 1  # 1 initial attempt + N repairs
        for round_no in range(1, rounds + 1):
            result = retryer(self._runnable.invoke, convo, **kwargs)
            parsed = result.get("parsed") if isinstance(result, dict) else result
            error = result.get("parsing_error") if isinstance(result, dict) else None
            if parsed is not None and error is None:
                return _as_model(parsed, self._schema)
            last_error = error
            logger.warning(
                "structured output for %s failed validation (round %d/%d): %s",
                self._schema.__name__,
                round_no,
                rounds,
                error,
            )
            raw = result.get("raw") if isinstance(result, dict) else None
            convo = convo + _repair_turn(raw, error, self._schema)
        raise StructuredOutputError(self._schema.__name__, last_error)


def _repair_turn(raw: Any, error: BaseException | None, schema: type) -> list[Any]:
    """The correction we feed back: the model's failed turn + a pointed fix request."""
    turns: list[Any] = []
    if raw is not None:
        turns.append(raw)  # show the model the exact output that failed
    turns.append(
        HumanMessage(
            content=(
                f"Your previous response did not match the required {schema.__name__} schema "
                f"and failed validation with: {error}. Return a corrected response that satisfies "
                f"every field and constraint of the schema. Output only the structured result."
            )
        )
    )
    return turns


class LLMClient:
    """Wraps one chat model. Low temperature for stable, repeatable investigations."""

    def __init__(
        self,
        provider: str,
        model: str,
        temperature: float = 0.0,
        *,
        policy: RetryPolicy | None = None,
        chat_model: Any | None = None,
    ):
        # ``chat_model`` is an injection seam for offline tests (the engine never passes it).
        self._model = (
            chat_model
            if chat_model is not None
            else init_chat_model(f"{provider}:{model}", temperature=temperature)
        )
        self._policy = policy or RetryPolicy.from_env()

    def bind_tools(self, tools):
        return _RetryingRunnable(
            self._model.bind_tools(tools), self._policy, "tool-loop"
        )

    def structured(self, schema):
        return _StructuredCaller(self._model, schema, self._policy)


def get_client(
    provider: str, model: str, *, policy: RetryPolicy | None = None
) -> LLMClient:
    """Build the chat client for a real provider (e.g. ``google_genai``)."""
    ensure_google_key()
    return LLMClient(provider, model, policy=policy)
