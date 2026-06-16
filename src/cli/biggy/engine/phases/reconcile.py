"""RECONCILE — the deterministic comms pass (no LLM).

Runs after the verdict: summarises customer impact from in-window tickets, and cross-checks the
public status DRAFT against the confirmed cause (the 'correct the draft' callout). Same ``Phase``
contract as ``verify`` — more proof the abstraction isn't LLM-shaped. The logic lives in
``engine/comms.py``; this node just records the artifacts on the ledger."""

from __future__ import annotations

from dataclasses import dataclass

from biggy.engine.comms import assess_impact, check_status
from biggy.engine.context import Investigation


@dataclass
class Reconcile:
    name: str = "reconcile"

    def run(self, inv: Investigation) -> None:
        inv.ledger.impact = assess_impact(inv.vault)
        if inv.ledger.result is not None:
            inv.ledger.status_check = check_status(inv.vault, inv.ledger.result)
