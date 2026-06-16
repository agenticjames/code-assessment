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
from biggy.engine.schemas import InvestigationResult

console = Console()


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


def _briefing(result: InvestigationResult, ledger: Ledger) -> Group:
    parts: list = [
        Panel(
            escape(result.summary),
            title="[bold]Investigation briefing[/]",
            subtitle=f"[dim]{escape(ledger.query)}[/]",
            border_style="cyan",
            expand=False,
        )
    ]
    ranked = sorted(result.hypotheses, key=lambda h: -h.confidence)
    for i, h in enumerate(ranked, 1):
        t = Table(show_header=False, box=None, pad_edge=False)
        t.add_column(style="cyan", no_wrap=True)
        t.add_column()
        t.add_row("service", escape(h.service or "-"))
        t.add_row("confidence", _conf_bar(h.confidence))
        t.add_row("statement", escape(h.statement))
        if h.evidence:
            ev = "\n".join(
                f'- {escape(e.claim)}\n  [dim]{escape(e.source)}[/] "{escape(e.snippet)}"'
                for e in h.evidence
            )
            t.add_row("evidence", ev)
        parts.append(
            Panel(
                t,
                title=f"[bold]Hypothesis {i}[/]",
                border_style="green" if i == 1 else "white",
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
    parts.append(Text(f"tool calls: {len(ledger.tool_calls)}", style="dim"))
    return Group(*parts)
