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


@dataclass
class Adjudicate:
    name: str = "adjudicate"

    def run(self, inv: Investigation) -> None:
        messages = inv.transcript + [HumanMessage(content=load_prompt("adjudicate"))]
        verdict = inv.llm.structured(InvestigationResult).invoke(messages)
        if isinstance(verdict, dict):
            verdict = InvestigationResult.model_validate(verdict)
        inv.ledger.result = verdict
