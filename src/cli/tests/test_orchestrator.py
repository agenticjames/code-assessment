"""The abductive loop end-to-end with a REAL Gemini call: it must confirm the rate-limiter AND
explicitly rule out the orders-db herring.

Skipped automatically when no API key is present (see the ``needs_llm`` fixture)."""

from __future__ import annotations

from biggy.engine.ledger import Ledger
from biggy.engine.orchestrator import investigate
from biggy.engine.trace import Tracer


def test_live_abductive_rules_out_herring(config_a, needs_llm, tmp_path):
    result, ledger = investigate(config_a, tracer=Tracer(enabled=False))

    # multi-hypothesis: it considered more than one candidate
    assert len(result.hypotheses) >= 2

    # the rate-limiter is the confirmed, top hypothesis
    top = max(result.hypotheses, key=lambda h: h.confidence)
    assert (top.service or "").lower() == "rate-limiter"
    assert top.status == "confirmed"

    # the orders-db migration herring is present AND explicitly ruled out, with a reason
    herring = next(
        (h for h in result.hypotheses if (h.service or "").lower() == "orders-db"), None
    )
    assert herring is not None, (
        "the agent should have considered the orders-db migration"
    )
    assert herring.status == "ruled_out"
    assert herring.ruled_out_reason

    # claims are cited from real telemetry; the ledger evolved and round-trips
    sources = [
        e.source for h in result.hypotheses for e in (h.supporting + h.contradicting)
    ]
    assert any(s.startswith("telemetry/") for s in sources)
    assert ledger.initial_hypotheses and ledger.tool_calls
    reloaded = Ledger.load(ledger.to_json(tmp_path / "ledger.json"))
    assert reloaded.result is not None and reloaded.query == config_a.query
