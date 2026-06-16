"""Offline grader tests — root_cause + inconclusive grading is deterministic (no LLM).

Synthetic ledgers are graded against the REAL HIDDEN_TRUTH keys, so these lock both the grading
logic and our reading of the answer-key schema."""

from __future__ import annotations

from pathlib import Path

from biggy.engine.ledger import Ledger
from biggy.engine.schemas import EvidenceRef, Grounding, Hypothesis, InvestigationResult
from biggy.eval.grade import grade

SCEN = (
    Path(__file__).resolve().parents[3] / "workspaces" / "acme-checkout" / "scenarios"
)


def _ev(source: str) -> EvidenceRef:
    return EvidenceRef(claim="c", snippet="s", source=source, verified=True)


def _ledger(scenario: str, result: InvestigationResult, grounded: int) -> Ledger:
    return Ledger(
        incident_id=f"acme-checkout-{scenario}",
        workspace="acme-checkout",
        scenario=scenario,
        query="q",
        result=result,
        grounding=Grounding(
            claims_total=grounded, claims_verified=grounded, ungrounded=[]
        ),
    )


def _fails(card):
    return [(c.name, c.detail) for c in card.checks if not c.ok]


def test_root_cause_scorecard_all_pass():
    res = InvestigationResult(
        query="q",
        outcome="root_cause",
        summary="s",
        hypotheses=[
            Hypothesis(
                id="H1",
                statement="rate-limiter exhausted redis",
                service="rate-limiter",
                confidence=0.9,
                status="confirmed",
                supporting=[_ev("telemetry/logs/redis.log:59")],
            ),
            Hypothesis(
                id="H2",
                statement="db migration",
                service="orders-db",
                confidence=0.05,
                status="ruled_out",
                ruled_out_reason="timing",
                contradicting=[_ev("telemetry/deploys.yaml:52")],
            ),
        ],
    )
    card = grade(_ledger("A", res, 2), SCEN / "A-checkout-504" / "HIDDEN_TRUTH.md")
    assert card.outcome_kind == "root_cause"
    assert card.passed, _fails(card)


def test_herring_credited_when_not_entertained():
    # Scenario B: the agent names auth-service and never lists the orders-db herring at all.
    res = InvestigationResult(
        query="q",
        outcome="root_cause",
        summary="s",
        hypotheses=[
            Hypothesis(
                id="H1",
                statement="auth OOM cascade",
                service="auth-service",
                confidence=0.9,
                status="confirmed",
                supporting=[_ev("telemetry/logs/auth-service.log:1")],
            )
        ],
    )
    card = grade(_ledger("B", res, 1), SCEN / "B-alert-storm" / "HIDDEN_TRUTH.md")
    herring = next(c for c in card.checks if c.name == "herring not chosen")
    assert herring.ok, herring.detail  # absent herring still counts as "not misled"


def test_inconclusive_passes_when_calibrated():
    res = InvestigationResult(
        query="q",
        outcome="inconclusive",
        summary="s",
        open_questions=[
            "need GC logs to confirm H1",
            "need traces/kafka logs to confirm H2",
        ],
        hypotheses=[
            Hypothesis(
                id="H1",
                statement="GC stalls",
                service="orders",
                confidence=0.52,
                status="open",
                supporting=[_ev("telemetry/logs/orders.log:1")],
            ),
            Hypothesis(
                id="H2",
                statement="flaky downstream",
                service="kafka",
                confidence=0.45,
                status="open",
                supporting=[_ev("telemetry/logs/orders.log:2")],
            ),
        ],
    )
    card = grade(_ledger("C", res, 2), SCEN / "C-intermittent-500" / "HIDDEN_TRUTH.md")
    assert card.outcome_kind == "inconclusive"
    assert card.passed, _fails(card)


def test_inconclusive_fails_when_overconfident():
    res = InvestigationResult(
        query="q",
        outcome="root_cause",
        summary="s",
        hypotheses=[
            Hypothesis(
                id="H1",
                statement="confidently wrong",
                service="orders",
                confidence=0.95,
                status="confirmed",
                supporting=[_ev("telemetry/logs/orders.log:1")],
            )
        ],
    )
    card = grade(_ledger("C", res, 1), SCEN / "C-intermittent-500" / "HIDDEN_TRUTH.md")
    assert not card.passed  # wrong outcome + over-confident => calibration failure
