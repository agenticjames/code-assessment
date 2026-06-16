"""Terminal briefing renderer (rich) + ledger persistence.

ASCII-only in our own strings (rich downgrades box-drawing on legacy Windows consoles, but our
literals must stay cp1252-safe). All LLM-produced text is markup-escaped before rendering.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console, Group
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from biggy.engine.config import RunConfig
from biggy.engine.ledger import Ledger
from biggy.engine.schemas import (
    CustomerImpact,
    EvidenceRef,
    Grounding,
    Hypothesis,
    InvestigationResult,
    StatusCheck,
)

console = Console()

_STATUS = {
    "confirmed": "[green]confirmed[/]",
    "ruled_out": "[red]ruled out[/]",
    "open": "[yellow]open[/]",
}
_BORDER = {"confirmed": "green", "ruled_out": "red", "open": "white"}


def render(result: InvestigationResult, ledger: Ledger, config: RunConfig) -> Path:
    """Print the briefing and write ledger.json; returns the ledger path."""
    console.print(_briefing(result, ledger))
    out_dir = (
        Path(config.out_dir) if config.out_dir else Path("runs") / ledger.incident_id
    )
    path = ledger.to_json(out_dir / "ledger.json")
    console.print(f"\n[dim]ledger -> {path}[/]")
    return path


def _conf_bar(c: float) -> str:
    return f"{c:.2f}  [{'#' * round(c * 10):<10}]"


def _evidence(refs: list[EvidenceRef]) -> str:
    lines = []
    for e in refs:
        if e.verified is None:
            tag = ""
        elif e.verified:
            tag = " [green][verified][/]"
        else:
            tag = " [red][UNVERIFIED][/]"
        lines.append(
            f'- {escape(e.claim)}{tag}\n  [dim]{escape(e.source)}[/] "{escape(e.snippet)}"'
        )
    return "\n".join(lines)


def _grounding_panel(g: Grounding) -> Panel:
    clean = g.claims_total > 0 and g.claims_verified == g.claims_total
    head = f"{g.claims_verified}/{g.claims_total} claims verified"
    body = f"[green]{head}[/]" if clean else f"[yellow]{head}[/]"
    if g.ungrounded:
        body += "\n" + "\n".join(
            f"[red]UNVERIFIED[/] {escape(u)}" for u in g.ungrounded
        )
    return Panel(
        body,
        title="[bold]Grounding[/] [dim](deterministic citation verifier)[/]",
        border_style="green" if clean else "yellow",
        expand=False,
    )


def _impact_panel(im: CustomerImpact) -> Panel:
    bits = [f"{im.ticket_count} support ticket(s)"]
    if im.top_priority:
        bits.append(f"top priority [bold]{escape(im.top_priority)}[/]")
    if im.services:
        bits.append("affected: " + escape(", ".join(im.services)))
    if im.first_seen:
        bits.append(f"first report {escape(im.first_seen)}")
    body = "  |  ".join(bits)
    if im.revenue_note:
        body += f"\n[dim]{escape(im.revenue_note)}[/]"
    return Panel(
        body,
        title="[bold]Customer impact[/] [dim](deterministic, from support tickets)[/]",
        border_style="red",
        expand=False,
    )


def _status_panel(sc: StatusCheck) -> Panel:
    body = escape(sc.message or "")
    if sc.draft_source:
        body += f"\n[dim]draft: {escape(sc.draft_source)}[/]"
    return Panel(
        body,
        title="[bold]Status-page correction[/] [dim](public draft vs evidence)[/]",
        border_style="red",
        expand=False,
    )


def _hypothesis_panel(h: Hypothesis, rank: int) -> Panel:
    t = Table(show_header=False, box=None, pad_edge=False)
    t.add_column(style="cyan", no_wrap=True)
    t.add_column()
    t.add_row("service", escape(h.service or "-"))
    t.add_row("status", _STATUS.get(h.status, escape(h.status)))
    t.add_row("confidence", _conf_bar(h.confidence))
    t.add_row("statement", escape(h.statement))
    if h.status == "ruled_out" and h.ruled_out_reason:
        t.add_row("ruled out", escape(h.ruled_out_reason))
    if h.supporting:
        t.add_row("supporting", _evidence(h.supporting))
    if h.contradicting:
        t.add_row("contradicting", _evidence(h.contradicting))
    title = f"[bold]Hypothesis {rank}" + (f" - {escape(h.id)}" if h.id else "") + "[/]"
    return Panel(
        t, title=title, border_style=_BORDER.get(h.status, "white"), expand=False
    )


def _briefing(result: InvestigationResult, ledger: Ledger) -> Group:
    outcome = (
        "[green]root cause[/]"
        if result.outcome == "root_cause"
        else "[yellow]INCONCLUSIVE[/]"
    )
    parts: list = [
        Panel(
            escape(result.summary),
            title=f"[bold]Investigation briefing[/]  ({outcome})",
            subtitle=f"[dim]{escape(ledger.query)}[/]",
            border_style="cyan",
            expand=False,
        )
    ]
    if ledger.grounding is not None:
        parts.append(_grounding_panel(ledger.grounding))
    if ledger.impact is not None and ledger.impact.ticket_count > 0:
        parts.append(_impact_panel(ledger.impact))
    ranked = sorted(result.hypotheses, key=lambda h: -h.confidence)
    parts += [_hypothesis_panel(h, i) for i, h in enumerate(ranked, 1)]
    if result.open_questions:
        parts.append(
            Panel(
                "\n".join(f"- {escape(q)}" for q in result.open_questions),
                title="[bold]Open questions[/]",
                border_style="magenta",
                expand=False,
            )
        )
    if result.noise_dropped:
        parts.append(
            Panel(
                "\n".join(
                    f"- {escape(n.item)} [dim]-- {escape(n.reason)}[/]"
                    for n in result.noise_dropped
                ),
                title="[bold]Noise dropped[/] [dim](considered, then dismissed)[/]",
                border_style="dim",
                expand=False,
            )
        )
    if result.recommended_action:
        parts.append(
            Panel(
                escape(result.recommended_action),
                title="[bold]Recommended action[/]",
                border_style="yellow",
                expand=False,
            )
        )
    if ledger.status_check is not None and ledger.status_check.needs_correction:
        parts.append(_status_panel(ledger.status_check))
    if result.stakeholder_note:
        parts.append(
            Panel(
                escape(result.stakeholder_note),
                title="[bold]Stakeholder update[/] [dim](paste-ready)[/]",
                border_style="blue",
                expand=False,
            )
        )
    parts.append(Text(f"tool calls: {len(ledger.tool_calls)}", style="dim"))
    return Group(*parts)
