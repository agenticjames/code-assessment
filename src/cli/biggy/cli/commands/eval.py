"""``biggy eval`` — run the engine across scenarios and score each against its HIDDEN_TRUTH.

The generalization proof: the same engine + general prompts on every scenario, graded objectively.
Each scenario's query comes from its own query.yaml; the answer key is read only by the grader.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

_out = Console()
_err = Console(stderr=True)


def run_eval(
    scenario: Optional[list[str]] = typer.Option(
        None,
        "--scenario",
        "-s",
        help="Scenario id(s) to run (repeatable); default = all discovered.",
    ),
    workspace: str = typer.Option(
        "acme-checkout", "--workspace", "-w", help="Workspace to evaluate."
    ),
    provider: str = typer.Option(
        "google_genai", "--provider", help="LLM provider (LangChain init_chat_model)."
    ),
    model: str = typer.Option(
        "gemini-3.1-flash-lite", "--model", "-m", help="Model id for the provider."
    ),
    out: Optional[Path] = typer.Option(
        None, "--out", help="Directory to write each scenario's ledger.json."
    ),
    detail: bool = typer.Option(
        True, "--detail/--no-detail", help="Show the per-scenario check breakdown."
    ),
    workspaces_root: Optional[Path] = typer.Option(
        None, "--workspaces-root", hidden=True
    ),
) -> None:
    """Score the engine across scenarios vs each HIDDEN_TRUTH (I-measure-my-agent)."""
    from dotenv import find_dotenv, load_dotenv

    from biggy.engine.llm.client import ensure_google_key
    from biggy.eval.grade import scorecard_panel
    from biggy.eval.harness import discover_scenarios, run_one, summary_panel

    load_dotenv(find_dotenv(usecwd=True))
    ensure_google_key()
    if not os.environ.get("GOOGLE_API_KEY"):
        _err.print(
            "[red]No API key found.[/] Put GEMINI_API_KEY (or GOOGLE_API_KEY) in a .env file "
            "at the repo root (see .env.example)."
        )
        raise typer.Exit(code=2)

    scenarios = scenario or discover_scenarios(workspace, workspaces_root)
    if not scenarios:
        _err.print("[red]No scenarios found.[/]")
        raise typer.Exit(code=2)

    runs = []
    for i, sid in enumerate(scenarios, 1):
        _err.print(f"[dim]running {i}/{len(scenarios)}: scenario {sid}…[/]")
        runs.append(
            run_one(
                sid,
                provider=provider,
                model=model,
                workspace=workspace,
                workspaces_root=workspaces_root,
                out_dir=out,
            )
        )

    if detail:
        for r in runs:
            if r.scorecard is not None:
                _out.print(scorecard_panel(r.scorecard))
    _out.print(summary_panel(runs, model))

    if not all(r.passed for r in runs):
        raise typer.Exit(code=1)
