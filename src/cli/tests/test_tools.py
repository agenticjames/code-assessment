"""Evidence tools return source-attached, time-scoped results. All offline (no LLM)."""

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


def test_get_topology_shows_shared_pool_and_dependents(config_a):
    out = _tools(config_a)["get_topology"].invoke({"service": "redis"})
    assert "shared_by" in out and "rate-limiter" in out and "checkout" in out
    assert "dependents" in out  # derived by inversion


def test_get_changes_is_windowed_to_the_incident(config_a):
    out = _tools(config_a)["get_changes"].invoke({})
    assert "dep-7e2a" in out and "mig-0616" in out  # the two afternoon candidates
    assert "dep-3a8c" not in out  # the 06-10 auth change is out of the window


def test_get_metric_summarises_the_spike_with_source(config_a):
    out = _tools(config_a)["get_metric"].invoke({"name": "checkout_p99"})
    assert "peak=" in out
    assert "telemetry/metrics/checkout_p99.csv:" in out
