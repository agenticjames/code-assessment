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
        sc = inv.vault.scenario
        context = (
            f"Incident: {sc.query!r} (severity {sc.severity or 'unknown'}); as of "
            f"{sc.as_of:%Y-%m-%dT%H:%M}Z, window {sc.window[0]:%H:%M}-{sc.window[1]:%H:%M}Z.\n\n"
            f"## Evidence manifest\n{inv.vault.list_evidence()}\n\n"
            f"## Changes in the window\n{inv.vault.get_changes()}"
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
