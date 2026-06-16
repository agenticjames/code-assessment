"""VERIFY — the deterministic citation-grounding phase (no LLM).

A thin pipeline node: it runs the citation verifier over the adjudicated verdict, records the
grounding score on the ledger, and flags ungrounded claims. The matching logic lives in
``engine/grounding.py``. Same ``Phase`` contract as the reasoning phases — proof the abstraction
isn't LLM-shaped.
"""

from __future__ import annotations

from dataclasses import dataclass

from biggy.engine.context import Investigation
from biggy.engine.grounding import verify_citations


@dataclass
class Verify:
    name: str = "verify"

    def run(self, inv: Investigation) -> None:
        if inv.ledger.result is None:
            return
        grounding = verify_citations(inv.ledger.result, inv.vault)
        inv.ledger.grounding = grounding
        inv.tracer.grounding(grounding.claims_verified, grounding.claims_total)
