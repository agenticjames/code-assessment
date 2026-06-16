"""``biggy investigate`` — the main command.

Scaffold stub: validates and echoes the resolved run configuration, then prints a
placeholder where the grounded briefing will appear once the engine is wired
(see ``../../docs/DELIVERY.md``, Inc 0+). It performs **no** file, network, or LLM
access.

The signature mirrors ``../../docs/ARCHITECTURE.md`` §6 so wiring the engine in
later is a drop-in change rather than a CLI rewrite.
"""

from __future__ import annotations

import json as _json
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def investigate(
    query: str = typer.Argument(
        ...,
        metavar="QUERY",
        help='The incident report, e.g. "checkout is throwing 504s".',
    ),
    workspace: str = typer.Option(
        "acme-checkout", "--workspace", "-w", help="Workspace to investigate within."
    ),
    scenario: Optional[str] = typer.Option(
        None, "--scenario", "-s", help="Scenario id within the workspace, e.g. A."
    ),
    provider: str = typer.Option(
        "google_genai", "--provider", help="LLM provider (LangChain init_chat_model)."
    ),
    model: str = typer.Option(
        "gemini-2.0-flash", "--model", "-m", help="Model id for the provider."
    ),
    max_steps: int = typer.Option(
        12, "--max-steps", min=1, help="Tool-loop step budget."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit machine-readable JSON instead of rich output."
    ),
) -> None:
    """Investigate an incident from a vague report.

    [yellow]Scaffold stub[/] - the investigation engine is not wired up yet.
    """
    config = {
        "query": query,
        "workspace": workspace,
        "scenario": scenario,
        "provider": provider,
        "model": model,
        "max_steps": max_steps,
    }

    if json_output:
        typer.echo(
            _json.dumps({"status": "not_implemented", "config": config}, indent=2)
        )
        raise typer.Exit()

    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column("field", style="cyan", no_wrap=True)
    table.add_column("value", style="white")
    table.add_row("query", query)
    table.add_row("workspace", workspace)
    table.add_row("scenario", scenario or "[dim]none[/]")
    table.add_row("provider", provider)
    table.add_row("model", model)
    table.add_row("max steps", str(max_steps))

    console.print(
        Panel(
            table,
            title="[bold]biggy investigate[/]",
            subtitle="[dim]resolved run config[/]",
            border_style="cyan",
            expand=False,
        )
    )
    console.print(
        "\n[yellow]> engine not wired yet[/] - scaffold stub (see docs/DELIVERY.md, Inc 0).\n"
        "  The grounded briefing (ranked hypotheses, evidence, citations) will render here."
    )
