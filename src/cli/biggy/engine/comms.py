"""The deterministic comms pass (NO LLM) — turns the messy human signal into two grounded briefing
artifacts:

  * **customer impact** — summarised from in-window support tickets (blast radius / severity /
    revenue), so the briefing carries real impact instead of a guess;
  * **status-page correction** — the public status DRAFT cross-checked against the verdict, flagged
    when it blames a cause the evidence does not support.

Like the citation verifier (``grounding.py``), these are facts computed by code, not the model — the
answer to "where is deterministic code better than the agent?" applied to human comms. Both are
reused by the ``reconcile`` phase and would be reused by a future API."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from biggy.engine.schemas import CustomerImpact, InvestigationResult, StatusCheck

if TYPE_CHECKING:
    from biggy.engine.evidence.vault import Vault

_TICKETS = "telemetry/support-tickets.md"
_STATUS = "telemetry/status-updates.md"
_PRIORITY_RANK = {"urgent": 4, "high": 3, "normal": 2, "low": 1}
_FIELD = re.compile(r"^(\w+):\s*(.+)")  # 'priority: urgent' / 'service_area: checkout'
_ISO_TS = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?Z)")


def assess_impact(vault: "Vault") -> CustomerImpact:
    """Summarise in-window customer tickets into a grounded impact line (deterministic)."""
    rows = vault.windowed(_TICKETS)
    tickets = [(ln, txt) for ln, txt in rows if txt.lstrip().startswith("- ")]
    revenue = next(
        (
            txt.split("revenue note:", 1)[1].strip()
            for _, txt in rows
            if "revenue note:" in txt
        ),
        None,
    )
    services: list[str] = []
    priorities: list[str] = []
    first_seen: str | None = None
    sources: list[str] = []
    for ln, txt in tickets:
        fields = dict(
            m.groups() for part in txt.split("|") if (m := _FIELD.match(part.strip()))
        )
        if (svc := fields.get("service_area")) and svc not in services:
            services.append(svc)
        if pr := fields.get("priority"):
            priorities.append(pr)
        if (tm := _ISO_TS.search(txt)) and (first_seen is None or tm.group(1) < first_seen):
            first_seen = tm.group(1)
        sources.append(f"{_TICKETS}:{ln}")
    return CustomerImpact(
        ticket_count=len(tickets),
        first_seen=first_seen,
        services=services,
        top_priority=max(priorities, key=lambda p: _PRIORITY_RANK.get(p, 0), default=None),
        revenue_note=revenue,
        sources=sources,
    )


def check_status(vault: "Vault", result: InvestigationResult) -> StatusCheck:
    """Cross-check an in-window public status DRAFT against the confirmed cause. A DRAFT that does
    not mention the confirmed cause is flagged for correction — the deterministic 'the public
    consensus is wrong' callout (no LLM)."""
    rows = vault.windowed(_STATUS)
    draft_ln: int | None = None
    excerpt_parts: list[str] = []
    capturing = False
    for ln, txt in rows:
        if "[DRAFT" in txt:
            draft_ln, capturing = ln, True
            excerpt_parts = [txt.split("]", 1)[-1].strip().strip('"')]
        elif capturing:
            s = txt.strip()
            if s.startswith("- ") or not s:  # next status entry / blank → draft ended
                capturing = False
            elif not s.startswith(">"):  # plain continuation = draft body ('>' = operator note)
                excerpt_parts.append(s.strip('"'))
    if draft_ln is None:
        return StatusCheck(has_draft=False)

    excerpt = " ".join(p for p in excerpt_parts if p)[:240]
    confirmed = next((h for h in result.hypotheses if h.status == "confirmed"), None)
    cause = confirmed.service if confirmed else None
    diverges = bool(cause) and cause.lower() not in excerpt.lower()
    message = (
        f'The public status draft does not reflect the investigation: it reads "{excerpt}", '
        f"but the evidence points to {cause}. Correct the draft before publishing."
        if diverges
        else None
    )
    return StatusCheck(
        has_draft=True,
        draft_source=f"{_STATUS}:{draft_ln}",
        draft_excerpt=excerpt,
        verdict_cause=cause,
        needs_correction=diverges,
        message=message,
    )
