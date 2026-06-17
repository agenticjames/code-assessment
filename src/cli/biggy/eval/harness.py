"""The eval harness — run the engine across scenarios and score each against its HIDDEN_TRUTH.

This is "I measure my agent": the **same** engine and the **same** general prompts on every
scenario, graded objectively. There is no scenario-specific logic anywhere — a scenario passes only
because the engine reasons correctly, which is what makes the scorecard a generalization proof.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from biggy.engine.config import RunConfig
from biggy.engine.orchestrator import investigate
from biggy.engine.scenario import hidden_truth_path
from biggy.engine.trace import Tracer
from biggy.eval.grade import Scorecard, grade


@dataclass
class EvalRun:
    scenario: str
    scorecard: Scorecard | None = None
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.scorecard is not None and self.scorecard.passed


def discover_scenarios(
    workspace: str = "acme-checkout", workspaces_root: Path | None = None
) -> list[str]:
    """Scenario ids (e.g. 'A') that have both a query.yaml and a HIDDEN_TRUTH.md."""
    sdir = (
        RunConfig(
            query="", workspace=workspace, workspaces_root=workspaces_root
        ).workspace_dir
        / "scenarios"
    )
    return [
        d.name.split("-")[0]
        for d in (sorted(sdir.iterdir()) if sdir.is_dir() else [])
        if d.is_dir()
        and (d / "query.yaml").is_file()
        and (d / "HIDDEN_TRUTH.md").is_file()
    ]


def run_one(
    scenario: str,
    *,
    provider: str,
    model: str,
    workspace: str = "acme-checkout",
    workspaces_root: Path | None = None,
    out_dir: Path | None = None,
    tracer: Tracer | None = None,
) -> EvalRun:
    """Run one scenario end-to-end (query comes from its query.yaml) and grade it. A broken or
    not-yet-ready scenario is captured as an error row rather than sinking the whole harness."""
    cfg = RunConfig(
        query="",
        workspace=workspace,
        scenario=scenario,
        provider=provider,
        model=model,
        workspaces_root=workspaces_root,
        out_dir=out_dir,
    )
    try:
        _, ledger = investigate(cfg, tracer=tracer or Tracer(enabled=False))
        if out_dir:
            ledger.to_json(Path(out_dir) / f"{ledger.incident_id}.json")
        ht = hidden_truth_path(cfg.workspace_dir, scenario)
        if ht is None:
            return EvalRun(scenario, error="no HIDDEN_TRUTH.md")
        return EvalRun(scenario, scorecard=grade(ledger, ht))
    except Exception as exc:  # noqa: BLE001 - one bad scenario must not abort the suite
        return EvalRun(scenario, error=f"{type(exc).__name__}: {exc}")


def summary_panel(runs: list[EvalRun], model: str) -> Panel:
    t = Table(box=None, pad_edge=False)
    t.add_column("scenario", style="cyan", no_wrap=True)
    t.add_column("kind")
    t.add_column("checks")
    t.add_column("result")
    n_pass = 0
    for r in runs:
        if r.scorecard is None:
            t.add_row(
                r.scenario, "-", "-", f"[red]ERROR[/] {escape((r.error or '')[:48])}"
            )
            continue
        c = r.scorecard
        n_pass += c.passed
        result = "[green]PASS[/]" if c.passed else "[yellow]FAIL[/]"
        t.add_row(r.scenario, c.outcome_kind, f"{c.n_passed}/{len(c.checks)}", result)
    return Panel(
        t,
        title=f"[bold]Eval scorecard[/] [dim](model {escape(model)})[/]",
        subtitle=f"[dim]{n_pass}/{len(runs)} scenarios pass[/]",
        border_style="green" if runs and n_pass == len(runs) else "yellow",
        expand=False,
    )
