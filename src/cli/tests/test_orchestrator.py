"""End-to-end thread with a REAL Gemini call: query -> tools over evidence -> cited verdict.

Skipped automatically when no API key is present (see the ``needs_llm`` fixture)."""

from __future__ import annotations

from biggy.engine.ledger import Ledger
from biggy.engine.orchestrator import investigate
from biggy.engine.trace import Tracer

_CITE_PREFIXES = (
    "telemetry/",
    "topology/",
    "runbooks/",
    "adr/",
    "monitors/",
    "slos.yaml",
    "teams.yaml",
)


def test_live_run_yields_cited_hypothesis(config_a, needs_llm, tmp_path):
    result, ledger = investigate(config_a, tracer=Tracer(enabled=False))

    assert result.hypotheses
    top = max(result.hypotheses, key=lambda h: h.confidence)
    # the culprit (rate-limiter) should be named, in the service field or the statement
    assert "rate-limiter" in f"{top.service or ''} {top.statement}".lower()

    sources = [e.source for h in result.hypotheses for e in h.evidence]
    assert sources, "every claim should be cited"
    assert any(s.startswith("telemetry/") for s in sources), (
        "should cite live telemetry"
    )
    assert all(s.startswith(_CITE_PREFIXES) for s in sources), (
        "citations must be real workspace paths"
    )
    assert ledger.tool_calls, "the agent should have used the tools"

    # the ledger artifact round-trips
    path = ledger.to_json(tmp_path / "ledger.json")
    reloaded = Ledger.load(path)
    assert reloaded.result is not None
    assert reloaded.query == config_a.query
