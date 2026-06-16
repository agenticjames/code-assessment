"""The orchestrator — composes the phases into a pipeline over a shared Investigation.

Plain Python, linear (ARCHITECTURE §3.1): each phase is a node-shaped object that mutates the
ledger. Adding a phase (verify in Inc 2, recall in Inc 5) is one entry in ``DEFAULT_PIPELINE``; a
LangGraph port maps each phase to a node.
"""

from __future__ import annotations

from collections.abc import Callable

from biggy.engine.config import RunConfig
from biggy.engine.context import Investigation
from biggy.engine.ledger import Ledger
from biggy.engine.phases import (
    Adjudicate,
    Hypothesize,
    Investigate,
    Phase,
    Reconcile,
    Verify,
)
from biggy.engine.schemas import InvestigationResult
from biggy.engine.trace import Tracer

DEFAULT_PIPELINE: list[Phase] = [
    Hypothesize(),
    Investigate(),
    Adjudicate(),
    Verify(),
    Reconcile(),
]


def investigate(
    config: RunConfig,
    tracer: Tracer | None = None,
    pipeline: list[Phase] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> tuple[InvestigationResult, Ledger]:
    """Run the phase pipeline and return the verdict + the (serialisable) ledger."""
    inv = Investigation.start(config, tracer, cancel_check)
    for phase in pipeline or DEFAULT_PIPELINE:
        inv.tracer.phase(phase.name)
        phase.run(inv)
    if inv.ledger.result is None:
        raise RuntimeError("pipeline finished without producing a verdict")
    return inv.ledger.result, inv.ledger
