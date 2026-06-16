"""Minimal per-step trace so you can watch the engine reason.

Writes to stderr so stdout stays clean (the briefing + any JSON pipe out cleanly). Inc 3
upgrades this to a live ``rich`` trace panel.
"""

from __future__ import annotations

from rich.console import Console

_console = Console(stderr=True)


class Tracer:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def scenario(self, vault) -> None:
        if not self.enabled:
            return
        sc = vault.scenario
        _console.print(
            f"[dim]investigating[/] {sc.query!r} [dim]as of[/] {sc.as_of:%H:%M}Z "
            f"[dim]({len(vault.manifest)} evidence files in window)[/]"
        )

    def tool_call(self, step: int, name: str, args: dict) -> None:
        if not self.enabled:
            return
        a = ", ".join(f"{k}={v!r}" for k, v in (args or {}).items())
        _console.print(f"[dim]  step {step}[/] [cyan]{name}[/]({a})")

    def thinking_done(self, step: int) -> None:
        if self.enabled:
            _console.print(f"[dim]  step {step}: done gathering — emitting verdict[/]")

    def budget_exhausted(self, n: int) -> None:
        if self.enabled:
            _console.print(
                f"[yellow]  step budget ({n}) exhausted — emitting best-effort verdict[/]"
            )

    def phase(self, name: str) -> None:
        if self.enabled:
            _console.print(f"[bold cyan]>> {name}[/]")

    def hypotheses(self, hyps) -> None:
        if not self.enabled:
            return
        for h in hyps:
            _console.print(
                f"[dim]  {h.id}[/] {h.statement} [dim](prior {h.confidence:.2f})[/]"
            )
