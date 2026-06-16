"""ADJUDICATE — turn the gathered evidence into the verdict.

A structured call over the test loop's transcript: each hypothesis marked confirmed/ruled_out with
supporting AND contradicting evidence, calibrated confidence, ruled-out reasons, and open questions.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import HumanMessage

from biggy.engine.context import Investigation
from biggy.engine.phases.base import load_prompt
from biggy.engine.schemas import InvestigationResult

# A triage first-pass leaves headroom for what it could not verify — it never asserts 100%.
_CONFIDENCE_CAP = 0.95


@dataclass
class Adjudicate:
    name: str = "adjudicate"

    def run(self, inv: Investigation) -> None:
        messages = inv.transcript + [HumanMessage(content=load_prompt("adjudicate"))]
        verdict = inv.llm.structured(InvestigationResult).invoke(messages)
        if isinstance(verdict, dict):
            verdict = InvestigationResult.model_validate(verdict)
        # Calibration guard: a triage first-pass should never claim certainty. Cap confidence at 0.95
        # deterministically so the badge stays honest even if the model ignores the prompt's ceiling.
        for h in verdict.hypotheses:
            if h.confidence > _CONFIDENCE_CAP:
                h.confidence = _CONFIDENCE_CAP
        # Coherence invariant: a 'root_cause' verdict requires a confirmed hypothesis. If the agent
        # confirmed nothing (all open/ruled_out), it is by definition inconclusive — enforce that.
        if verdict.outcome == "root_cause" and not any(
            h.status == "confirmed" for h in verdict.hypotheses
        ):
            verdict.outcome = "inconclusive"
        inv.ledger.result = verdict
        inv.tracer.verdict(verdict)
