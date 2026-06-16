"""The deterministic citation verifier (engine/grounding.py) — the trust centerpiece.

Offline + deterministic: it must verify a real quote and catch a planted fabricated one. This is the
proof the engine can't be bluffed past, independent of any LLM."""

from __future__ import annotations

from biggy.engine.evidence.vault import Vault
from biggy.engine.grounding import snippet_in_source, verify_citations
from biggy.engine.schemas import EvidenceRef, Hypothesis, InvestigationResult


def test_snippet_match_normalises_whitespace_and_case():
    assert snippet_in_source(
        "Max  Number\tof Clients", "redis: max number of clients reached"
    )
    assert not snippet_in_source(
        "totally not present anywhere", "something else entirely"
    )
    assert not snippet_in_source("x", None)  # ablated/missing source


def test_verifier_catches_a_planted_bad_citation(config_a):
    vault = Vault.load(config_a)
    result = InvestigationResult(
        query="checkout 504s",
        summary="s",
        hypotheses=[
            Hypothesis(
                id="H1",
                statement="rate-limiter exhausted the shared redis pool",
                service="rate-limiter",
                confidence=0.9,
                status="confirmed",
                supporting=[
                    EvidenceRef(
                        claim="redis hit its connection cap",
                        snippet="max number of clients reached",  # real — in redis.log
                        source="telemetry/logs/redis.log:59",
                    )
                ],
                contradicting=[
                    EvidenceRef(
                        claim="(planted) fabricated quote",
                        snippet="ZZZ this exact string appears in no file ZZZ",
                        source="telemetry/logs/redis.log:1",
                    )
                ],
            )
        ],
    )
    g = verify_citations(result, vault)
    assert g.claims_total == 2
    assert g.claims_verified == 1
    assert result.hypotheses[0].supporting[0].verified is True
    assert result.hypotheses[0].contradicting[0].verified is False
    assert any("fabricated" in u for u in g.ungrounded)
