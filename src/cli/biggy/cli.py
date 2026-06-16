"""Biggy CLI — the thin Typer shell.

Assembles the Typer app and registers commands. Holds no investigation logic: the
engine (added later) is imported by the command modules, so this shell stays a pure
entrypoint that a future API surface can reuse unchanged. See
``../../docs/ARCHITECTURE.md`` §3.4.
"""

from __future__ import annotations

import typer

from biggy import __version__
from biggy.commands import investigate, version

app = typer.Typer(
    name="biggy",
    help="Biggy - investigate messy production incidents and produce a briefing you can trust.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"biggy {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    _version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show the Biggy version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Biggy - an AI on-call incident-investigation copilot."""


# One module per command; each module exposes a plain function we register here.
app.command("investigate")(investigate.investigate)
app.command("version")(version.version)
