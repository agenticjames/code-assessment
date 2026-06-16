"""``biggy version`` — print version and environment info."""

from __future__ import annotations

import sys

import typer

from biggy import __version__


def version() -> None:
    """Show the Biggy version and Python runtime."""
    typer.echo(f"biggy {__version__}")
    typer.echo(f"python {sys.version.split()[0]}")
