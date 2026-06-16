"""Structured trace events + pluggable sinks (docs/PHASE2.md §3.2).

The engine emits *semantic* events through a ``Tracer`` to a ``TraceSink``. The CLI uses
``RichSink`` (stderr, byte-identical to Inc 0–2); the Phase 2 worker plugs in a sink that fans the
same events out to Redis (live stream) + Postgres (durable). The engine knows nothing about either
surface — it just calls ``tracer.<event>(...)``. This is the seam that lets one engine drive both
the terminal and the browser.

Every event is ``(type, data)`` where ``data`` is JSON-serialisable, so a sink can persist/publish
it verbatim. The ``type`` strings are the discriminated union shared with the web in
``src/web/lib/contracts.ts`` and mirrored in ``biggy/worker/contracts.py`` — keep them in sync.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from rich.console import Console

if TYPE_CHECKING:
    from biggy.engine.evidence.vault import Vault
    from biggy.engine.schemas import Hypothesis, InvestigationResult

# Event type names — the engine-emitted half of the union (the worker adds status/error/…/done).
EVENT_SCENARIO = "scenario"
EVENT_PHASE = "phase"
EVENT_HYPOTHESES = "hypotheses"
EVENT_TOOL_CALL = "tool_call"
EVENT_TOOL_RESULT = "tool_result"
EVENT_THINKING_DONE = "thinking_done"
EVENT_BUDGET_EXHAUSTED = "budget_exhausted"
EVENT_GROUNDING = "grounding"
EVENT_VERDICT = "verdict"

_PREVIEW_LIMIT = 280  # matches Ledger.record_tool, so stream + ledger previews agree.


def _truncate(text: str) -> str:
    return text if len(text) <= _PREVIEW_LIMIT else text[: _PREVIEW_LIMIT - 3] + "..."


@runtime_checkable
class TraceSink(Protocol):
    """Where trace events go. ``emit`` must be cheap/non-throwing (it's on the hot path)."""

    def emit(self, event_type: str, data: dict[str, Any]) -> None: ...


class NullSink:
    """Drops events — used when tracing is disabled (e.g. offline tests)."""

    def emit(self, event_type: str, data: dict[str, Any]) -> None:  # noqa: D102
        return None


_console = Console(stderr=True)


class RichSink:
    """The CLI sink — renders the live trace to stderr, byte-identical to the pre-seam Tracer.

    stdout stays clean (the briefing + any JSON pipe out cleanly). ``tool_result``/``verdict`` are
    intentionally silent here: the CLI shows tool *calls* live and renders the verdict via the
    separate briefing renderer, exactly as before.
    """

    def emit(self, event_type: str, data: dict[str, Any]) -> None:  # noqa: C901
        if event_type == EVENT_SCENARIO:
            as_of = datetime.fromisoformat(data["as_of"])
            _console.print(
                f"[dim]investigating[/] {data['query']!r} [dim]as of[/] {as_of:%H:%M}Z "
                f"[dim]({data['files']} evidence files in window)[/]"
            )
        elif event_type == EVENT_PHASE:
            _console.print(f"[bold cyan]>> {data['name']}[/]")
        elif event_type == EVENT_HYPOTHESES:
            for h in data["hypotheses"]:
                _console.print(
                    f"[dim]  {h['id']}[/] {h['statement']} [dim](prior {h['confidence']:.2f})[/]"
                )
        elif event_type == EVENT_TOOL_CALL:
            a = ", ".join(f"{k}={v!r}" for k, v in (data.get("args") or {}).items())
            _console.print(
                f"[dim]  step {data['step']}[/] [cyan]{data['name']}[/]({a})"
            )
        elif event_type == EVENT_THINKING_DONE:
            _console.print(
                f"[dim]  step {data['step']}: done gathering — emitting verdict[/]"
            )
        elif event_type == EVENT_BUDGET_EXHAUSTED:
            _console.print(
                f"[yellow]  step budget ({data['max_steps']}) exhausted — emitting "
                "best-effort verdict[/]"
            )
        elif event_type == EVENT_GROUNDING:
            verified, total = data["verified"], data["total"]
            colour = "green" if total and verified == total else "yellow"
            _console.print(
                f"[{colour}]  grounding: {verified}/{total} claims verified[/]"
            )
        # EVENT_TOOL_RESULT / EVENT_VERDICT: not shown in the CLI (see docstring).


class Tracer:
    """Typed event API the engine calls. Builds JSON-serialisable payloads and forwards to a sink.

    ``Tracer()`` → CLI (``RichSink``). ``Tracer(enabled=False)`` → ``NullSink`` (tests).
    ``Tracer(sink=...)`` → any sink (the worker's Redis+Postgres fan-out).
    """

    def __init__(self, sink: TraceSink | None = None, *, enabled: bool = True):
        if sink is None:
            sink = RichSink() if enabled else NullSink()
        self.sink = sink

    def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        self.sink.emit(event_type, data)

    def scenario(self, vault: "Vault") -> None:
        sc = vault.scenario
        start, end = sc.window
        self._emit(
            EVENT_SCENARIO,
            {
                "query": sc.query,
                "as_of": sc.as_of.isoformat(),
                "window": [start.isoformat(), end.isoformat()],
                "files": len(vault.manifest),
            },
        )

    def phase(self, name: str) -> None:
        self._emit(EVENT_PHASE, {"name": name})

    def hypotheses(self, hyps: "list[Hypothesis]") -> None:
        self._emit(
            EVENT_HYPOTHESES,
            {
                "hypotheses": [
                    {
                        "id": h.id,
                        "statement": h.statement,
                        "service": h.service,
                        "confidence": h.confidence,
                    }
                    for h in hyps
                ]
            },
        )

    def tool_call(self, step: int, name: str, args: dict) -> None:
        self._emit(EVENT_TOOL_CALL, {"step": step, "name": name, "args": args or {}})

    def tool_result(
        self, step: int, name: str, result: str, source: str | None = None
    ) -> None:
        self._emit(
            EVENT_TOOL_RESULT,
            {
                "step": step,
                "name": name,
                "preview": _truncate(result),
                "source": source,
            },
        )

    def thinking_done(self, step: int) -> None:
        self._emit(EVENT_THINKING_DONE, {"step": step})

    def budget_exhausted(self, n: int) -> None:
        self._emit(EVENT_BUDGET_EXHAUSTED, {"max_steps": n})

    def grounding(self, verified: int, total: int) -> None:
        self._emit(EVENT_GROUNDING, {"verified": verified, "total": total})

    def verdict(self, result: "InvestigationResult") -> None:
        data = result.model_dump() if hasattr(result, "model_dump") else dict(result)
        self._emit(EVENT_VERDICT, data)
