"""HYPOTHESIZE — propose a set of candidate causes (incl. the obvious one), each with a test.

A single structured call seeded with the manifest + the changes in the window. No tools yet; the
tool-driven reasoning happens in the test phase.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from biggy.engine.context import Investigation
from biggy.engine.phases.base import load_prompt
from biggy.engine.schemas import Hypotheses


@dataclass
class Hypothesize:
    name: str = "hypothesize"

    def run(self, inv: Investigation) -> None:
        v = inv.vault
        f = v.frame
        context = (
            f"Incident: {v.query!r} (severity {v.severity or 'unknown'}); as of "
            f"{f.as_of:%Y-%m-%dT%H:%M}Z, window {f.label()}.\n\n"
            f"## Evidence manifest\n{v.list_evidence(categories=('telemetry', 'standing'))}\n\n"
            f"## Changes in the window\n{v.get_changes()}"
        )
        msgs = [
            SystemMessage(content=load_prompt("hypothesize")),
            HumanMessage(content=context),
        ]
        hyps = inv.llm.structured(Hypotheses).invoke(msgs)
        if isinstance(hyps, dict):
            hyps = Hypotheses.model_validate(hyps)
        for i, h in enumerate(hyps.hypotheses, 1):
            if not h.id:
                h.id = f"H{i}"
            h.status = "open"
        inv.ledger.record_hypotheses(hyps.hypotheses)
        inv.tracer.hypotheses(hyps.hypotheses)
