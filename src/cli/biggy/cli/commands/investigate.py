"""``biggy investigate`` — run an incident investigation and print a grounded briefing.

Thin shell: load ``.env``, build a ``RunConfig`` from flags, hand off to the engine, render.
Heavy imports (engine, LangChain, dotenv) are deferred into the function so ``biggy --help`` and
``biggy version`` stay fast and import-light.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

_out = Console()
_err = Console(stderr=True)


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
        None,
        "--scenario",
        "-s",
        help="Scenario id to seed the frame + enable --check grading, e.g. A.",
    ),
    as_of: Optional[str] = typer.Option(
        None,
        "--as-of",
        help="Investigate as of this UTC instant (ISO 8601). Default: now.",
    ),
    look_back: Optional[str] = typer.Option(
        None,
        "--look-back",
        help="Window depth from --as-of, e.g. 2h / 90m / 5d. Default: 2h.",
    ),
    since: Optional[str] = typer.Option(
        None,
        "--since",
        help="Retrospective range start (ISO 8601); use with --until.",
    ),
    until: Optional[str] = typer.Option(
        None,
        "--until",
        help="Retrospective range end (ISO 8601); use with --since.",
    ),
    provider: str = typer.Option(
        "google_genai", "--provider", help="LLM provider (LangChain init_chat_model)."
    ),
    model: str = typer.Option(
        "gemini-3.1-flash-lite", "--model", "-m", help="Model id for the provider."
    ),
    max_steps: int = typer.Option(
        12, "--max-steps", min=1, help="Tool-loop step budget."
    ),
    out: Optional[Path] = typer.Option(
        None,
        "--out",
        help="Directory to write ledger.json (default: runs/<incident-id>).",
    ),
    check: bool = typer.Option(
        False,
        "--check",
        help="Grade the run against the scenario's HIDDEN_TRUTH answer key.",
    ),
    workspaces_root: Optional[Path] = typer.Option(
        None,
        "--workspaces-root",
        hidden=True,
        help="Override the workspaces/ root (else $BIGGY_WORKSPACES_ROOT or the in-repo default).",
    ),
    ablate: Optional[list[str]] = typer.Option(
        None,
        "--ablate",
        help="Hide an evidence path from the agent (repeatable) — the honesty demo, "
        "e.g. --ablate telemetry/logs/redis.log.",
    ),
) -> None:
    """Investigate an incident from a vague report and print a grounded briefing."""
    from dotenv import find_dotenv, load_dotenv

    from biggy.engine.config import RunConfig
    from biggy.cli.render import render

    load_dotenv(find_dotenv(usecwd=True))
    from biggy.engine.llm.client import ensure_google_key

    ensure_google_key()
    if not os.environ.get("GOOGLE_API_KEY"):
        _err.print(
            "[red]No API key found.[/] Put GEMINI_API_KEY (or GOOGLE_API_KEY) in a .env file "
            "at the repo root (see .env.example)."
        )
        raise typer.Exit(code=2)

    config = RunConfig(
        query=query,
        workspace=workspace,
        scenario=scenario,
        as_of=as_of,
        look_back=look_back,
        since=since,
        until=until,
        provider=provider,
        model=model,
        max_steps=max_steps,
        out_dir=out,
        workspaces_root=workspaces_root,
        ablate=ablate or [],
    )

    try:
        from biggy.engine.orchestrator import investigate as run_investigation

        result, ledger = run_investigation(config)
    except (FileNotFoundError, ValueError) as exc:
        _err.print(f"[red]{exc}[/]")
        raise typer.Exit(code=2) from exc

    render(result, ledger, config)

    if check:
        from biggy.eval.grade import grade, scorecard_panel
        from biggy.engine.scenario import hidden_truth_path

        if not config.scenario:
            _err.print(
                "[yellow]--check needs a --scenario (the answer key lives with it).[/]"
            )
        else:
            ht = hidden_truth_path(config.workspace_dir, config.scenario)
            if ht is None:
                _err.print(
                    "[yellow]No HIDDEN_TRUTH.md for this scenario — cannot grade.[/]"
                )
            else:
                _out.print(scorecard_panel(grade(ledger, ht)))
