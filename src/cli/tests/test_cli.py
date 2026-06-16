"""CLI smoke tests — all offline (no LLM, no network). The live engine path is covered by
``test_orchestrator`` (gated behind a Gemini key via the ``needs_llm`` fixture)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from biggy import __version__
from biggy.cli import app

runner = CliRunner()

# src/cli/tests/test_cli.py -> parents[3] is the repo root holding workspaces/.
WORKSPACES = Path(__file__).resolve().parents[3] / "workspaces"


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "investigate" in result.output
    assert "version" in result.output


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert f"biggy {__version__}" in result.output


def test_unknown_scenario_exits_2(tmp_path) -> None:
    # An unknown scenario (or a missing key) surfaces as a clean exit code 2, not a traceback. It
    # short-circuits in Vault.load before any LLM call, so this stays offline regardless of a key.
    result = runner.invoke(
        app,
        [
            "investigate",
            "checkout is throwing 504s",
            "-s",
            "ZZZ",
            "--workspaces-root",
            str(WORKSPACES),
            "--out",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 2
