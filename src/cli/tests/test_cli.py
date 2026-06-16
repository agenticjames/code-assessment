"""Smoke tests for the Biggy CLI scaffold (no engine, no network)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from biggy import __version__
from biggy.cli import app

runner = CliRunner()


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


def test_investigate_stub_renders_config() -> None:
    result = runner.invoke(
        app, ["investigate", "checkout is throwing 504s", "--scenario", "A"]
    )
    assert result.exit_code == 0
    assert "504s" in result.output
    assert "acme-checkout" in result.output  # default workspace echoed


def test_investigate_json_is_not_implemented() -> None:
    result = runner.invoke(app, ["investigate", "x", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "not_implemented"
    assert payload["config"]["query"] == "x"
