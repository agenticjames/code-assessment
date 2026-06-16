"""Vault time-scoping + answer-key isolation — the load-bearing Inc 0 correctness properties.

All offline (no LLM)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from biggy.engine.config import RunConfig
from biggy.engine.evidence.vault import Vault


def test_window_is_as_of_minus_lookback(config_a):
    sc = Vault.load(config_a).scenario
    assert sc.as_of == datetime(2026, 6, 16, 15, 15, tzinfo=timezone.utc)
    assert sc.window[0] == datetime(2026, 6, 16, 13, 15, tzinfo=timezone.utc)


def test_other_incidents_excluded_by_window(config_a):
    v = Vault.load(config_a)
    full = (v.root / "telemetry" / "logs" / "redis.log").read_text(encoding="utf-8")
    windowed = v.read_evidence("telemetry/logs/redis.log")
    # the smoking gun is inside the window...
    assert "max number of clients reached" in windowed
    # ...but the 06-10 auth-incident traffic in the same file is sliced out.
    assert "10 Jun 2026" in full
    assert "10 Jun 2026" not in windowed


def test_hidden_truth_is_never_exposed(config_a):
    v = Vault.load(config_a)
    assert all("HIDDEN_TRUTH" not in e.relpath for e in v.manifest)
    assert all(not e.relpath.startswith("scenarios/") for e in v.manifest)
    assert "ERROR" in v.read_evidence("scenarios/A-checkout-504/HIDDEN_TRUTH.md")


def test_missing_scenario_raises(ws_root):
    cfg = RunConfig(
        query="x", workspace="acme-checkout", scenario=None, workspaces_root=ws_root
    )
    with pytest.raises(ValueError):
        Vault.load(cfg)


def test_unknown_scenario_raises(ws_root):
    cfg = RunConfig(
        query="x", workspace="acme-checkout", scenario="ZZZ", workspaces_root=ws_root
    )
    with pytest.raises(FileNotFoundError):
        Vault.load(cfg)


def test_raw_text_resolves_and_guards(config_a):
    v = Vault.load(config_a)
    assert "max number of clients reached" in (
        v.raw_text("telemetry/logs/redis.log:59") or ""
    )
    assert (
        v.raw_text("scenarios/A-checkout-504/HIDDEN_TRUTH.md") is None
    )  # answer key guarded
    assert v.raw_text("nope/missing.log") is None


def test_ablation_hides_file_from_manifest_and_verifier(ws_root):
    cfg = RunConfig(
        query="x",
        workspace="acme-checkout",
        scenario="A",
        workspaces_root=ws_root,
        ablate=["telemetry/logs/redis.log"],
    )
    v = Vault.load(cfg)
    assert all(e.relpath != "telemetry/logs/redis.log" for e in v.manifest)
    assert v.raw_text("telemetry/logs/redis.log") is None
