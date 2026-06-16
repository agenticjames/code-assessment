"""Offline grader tests — root_cause + inconclusive grading is deterministic (no LLM).

Synthetic ledgers are graded against the REAL HIDDEN_TRUTH keys, so these lock both the grading
logic and our reading of the answer-key schema."""

from __future__ import annotations

from pathlib import Path

from biggy.engine.ledger import Ledger
from biggy.engine.schemas import (
    EvidenceRef,
    Grounding,
    Hypothesis,
    InvestigationResult,
    NoiseItem,
    StatusCheck,
)
from biggy.eval.grade import grade

SCEN = (
    Path(__file__).resolve().parents[3] / "workspaces" / "acme-checkout" / "scenarios"
)


def _ev(source: str, claim: str = "c", snippet: str = "s") -> EvidenceRef:
    return EvidenceRef(claim=claim, snippet=snippet, source=source, verified=True)


def _ledger(
    scenario: str,
    result: InvestigationResult,
    grounded: int,
    status_check: StatusCheck | None = None,
) -> Ledger:
    return Ledger(
        incident_id=f"acme-checkout-{scenario}",
        workspace="acme-checkout",
        scenario=scenario,
        query="q",
        result=result,
        grounding=Grounding(
            claims_total=grounded, claims_verified=grounded, ungrounded=[]
        ),
        status_check=status_check,
    )


def _fails(card):
    return [(c.name, c.detail) for c in card.checks if not c.ok]


def test_root_cause_scorecard_all_pass():
    res = InvestigationResult(
        query="q",
        outcome="root_cause",
        summary="rate-limiter exhausted redis; this matches INC-0987.",
        open_questions=[
            "no canary metrics were captured for dep-7e2a before it went to prod",
            "cart shares redis too, but whether cart was undetected or unaffected is unknown",
        ],
        noise_dropped=[
            NoiseItem(
                item="disk-space-low SEV4 on log-aggregator",
                reason="chronic alert firing for days and unrelated to checkout traffic",
            )
        ],
        hypotheses=[
            Hypothesis(
                id="H1",
                statement="rate-limiter exhausted redis",
                service="rate-limiter",
                confidence=0.9,
                status="confirmed",
                supporting=[
                    _ev(
                        "telemetry/changes/dep-7e2a.diff:9",
                        snippet="- max_tokens: 100\n+ max_tokens: 10",
                    ),
                    _ev(
                        "telemetry/logs/redis.log:59",
                        snippet="max number of clients reached",
                    ),
                    _ev("telemetry/deploys.yaml:52", snippet="dep-7e2a"),
                    _ev(
                        "telemetry/captures/2026-06-16T1450Z-redis-cli-info.txt:4",
                        snippet="connected_clients:50\nmaxclients:50",
                    ),
                    _ev(
                        "incident-library/INC-0987-redis-pool-flash-sale.md:1",
                        claim="INC-0987 is the same failure class",
                        snippet="INC-0987",
                    ),
                ],
            ),
            Hypothesis(
                id="H2",
                statement="db migration",
                service="orders-db",
                confidence=0.05,
                status="ruled_out",
                ruled_out_reason="timing gap and rollback did not stop the 504s",
                contradicting=[_ev("telemetry/deploys.yaml:52", snippet="rollback")],
            ),
        ],
    )
    card = grade(
        _ledger(
            "A",
            res,
            7,
            status_check=StatusCheck(
                has_draft=True,
                needs_correction=True,
                draft_source="telemetry/status-updates.md:14",
                verdict_cause="rate-limiter",
            ),
        ),
        SCEN / "A-checkout-504" / "HIDDEN_TRUTH.md",
    )
    assert card.outcome_kind == "root_cause"
    assert card.passed, _fails(card)


def test_herring_must_be_explicitly_ruled_out_with_reason():
    # The assessment story says the agent considers and rejects herrings. Merely omitting the
    # herring is not enough for the richer scorecard.
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
    herring = next(c for c in card.checks if c.name == "herring ruled out")
    assert not herring.ok, herring.detail


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
                statement="orders memory pressure could be causing GC stalls",
                service="orders",
                confidence=0.52,
                status="open",
                supporting=[
                    _ev(
                        "telemetry/logs/orders.log:1",
                        snippet="gc.logging=disabled",
                    ),
                    _ev(
                        "telemetry/logs/orders.log:2",
                        snippet="tracing.sample_rate=0.01",
                    ),
                    _ev("telemetry/metrics/orders_memory.csv:1"),
                ],
            ),
            Hypothesis(
                id="H2",
                statement="flaky downstream dependency, with kafka the prime suspect",
                service="kafka",
                confidence=0.45,
                status="open",
                supporting=[
                    _ev(
                        "telemetry/logs/orders.log:3",
                        snippet="downstream call timed out after 3000ms",
                    ),
                    _ev(
                        "telemetry/deploys.yaml:1",
                        claim="no change in the 2026-06-15 window",
                        snippet="last orders deploy dep-2b40 @2026-06-09",
                    ),
                ],
            ),
        ],
        noise_dropped=[
            NoiseItem(item="benign error-rate blips at 16:33 and 16:38", reason="below spike level"),
            NoiseItem(
                item="NullPointerException and IllegalStateException",
                reason="could be a latent code bug, not proof for either hypothesis",
            ),
            NoiseItem(item="orders CPU", reason="unremarkable and no trend"),
        ],
    )
    card = grade(_ledger("C", res, 5), SCEN / "C-intermittent-500" / "HIDDEN_TRUTH.md")
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
