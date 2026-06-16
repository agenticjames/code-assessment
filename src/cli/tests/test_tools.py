"""Evidence tools return source-attached, time-scoped results."""

from __future__ import annotations

from biggy.engine.evidence.tools import make_tools
from biggy.engine.evidence.vault import Vault


def _tools(config_a):
    return {t.name: t for t in make_tools(Vault.load(config_a))}


def test_search_finds_redis_saturation_with_source(config_a):
    out = _tools(config_a)["search"].invoke(
        {"keyword": "max number of clients reached"}
    )
    assert "telemetry/logs/redis.log:" in out  # path:line provenance attached


def test_read_file_returns_the_mechanism(config_a):
    out = _tools(config_a)["read_file"].invoke(
        {"path": "telemetry/changes/dep-7e2a.diff"}
    )
    assert "max_tokens" in out


def test_list_evidence_covers_telemetry_and_standing(config_a):
    out = _tools(config_a)["list_evidence"].invoke({})
    assert "telemetry/logs/redis.log" in out
    assert "topology/services.yaml" in out
