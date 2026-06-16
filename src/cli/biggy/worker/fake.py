"""``BIGGY_FAKE_RUN`` — a keyless, deterministic stand-in for the LLM investigation (PHASE2 §7/§10).

Replays a canonical Scenario-A investigation: the REAL vault + REAL tools + the REAL citation
verifier, with only the LLM's hypotheses + verdict synthesized. Lets the whole web pipeline
(enqueue -> worker -> stream -> UI) run without a Gemini key, and backs the worker's offline e2e
test. ``fn(config, tracer, cancel_check)`` — the same shape ``run_job`` injects.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable

from biggy.engine.config import RunConfig
from biggy.engine.context import InvestigationCancelled
from biggy.engine.evidence.tools import make_tools
from biggy.engine.evidence.vault import Vault
from biggy.engine.grounding import verify_citations
from biggy.engine.ledger import Ledger
from biggy.engine.schemas import (
    EvidenceRef,
    Hypothesis,
    InvestigationResult,
    NoiseItem,
)
from biggy.engine.trace import Tracer

_DELAY = float(os.environ.get("BIGGY_FAKE_DELAY", "0.4"))

# A believable evidence-gathering sequence over the real Scenario-A vault.
_STEPS: list[tuple[str, dict]] = [
    ("list_evidence", {}),
    ("read_file", {"path": "telemetry/alerts.jsonl"}),
    ("read_file", {"path": "telemetry/changes/dep-7e2a.diff"}),
    ("get_topology", {"service": "checkout"}),
    ("read_file", {"path": "adr/ADR-014-shared-redis.md"}),
]


def _initial_hypotheses() -> list[Hypothesis]:
    return [
        Hypothesis(
            id="H1",
            statement="A rate-limiter config change exhausted the shared Redis pool, starving checkout.",
            service="rate-limiter",
            confidence=0.4,
            disconfirming_test="If DB latency is flat and the migration rollback didn't help, the migration is innocent.",
        ),
        Hypothesis(
            id="H2",
            statement="The orders-db migration caused the checkout 504s.",
            service="orders-db",
            confidence=0.4,
            disconfirming_test="Check whether the 14:58 rollback resolved the symptom and whether DB latency moved.",
        ),
    ]


def _verdict(query: str) -> InvestigationResult:
    return InvestigationResult(
        query=query,
        outcome="root_cause",
        summary=(
            "A rate-limiter config change at 14:45Z cut the token bucket, surging the shared Redis "
            "pool to saturation; checkout's connection acquisitions timed out as 504s. The orders-db "
            "migration is ruled out."
        ),
        recommended_action="Roll back dep-7e2a to restore the rate-limiter max_tokens (100).",
        stakeholder_note=(
            "Checkout is returning 504s for a subset of customers. Most likely cause (high "
            "confidence): a 14:45Z rate-limiter config change (dep-7e2a) exhausted the shared Redis "
            "connection pool; the earlier orders-db migration has been ruled out. We are rolling back "
            "dep-7e2a now and will confirm recovery."
        ),
        open_questions=[
            "No canary logs exist for dep-7e2a to confirm the rollout timing precisely."
        ],
        noise_dropped=[
            NoiseItem(
                item="disk-space SEV4 on log-aggregator",
                reason="chronic pre-incident alert, unrelated to the 504 onset.",
            ),
        ],
        hypotheses=[
            Hypothesis(
                id="H1",
                statement="The rate-limiter change (dep-7e2a) exhausted the shared Redis pool.",
                service="rate-limiter",
                confidence=0.82,
                status="confirmed",
                disconfirming_test="DB latency flat + migration rollback ineffective.",
                supporting=[
                    EvidenceRef(
                        claim="The rate-limiter max_tokens was cut 100 -> 10.",
                        snippet="max_tokens: 10",
                        source="telemetry/changes/dep-7e2a.diff:9",
                    ),
                    EvidenceRef(
                        claim="The shared Redis pool saturated shortly after the change.",
                        snippet="redis-connections-saturated",
                        source="telemetry/alerts.jsonl:26",
                    ),
                    EvidenceRef(
                        claim="rate-limiter, checkout and cart share one Redis pool.",
                        snippet="rate-limiter, checkout, and cart",
                        source="adr/ADR-014-shared-redis.md:1",
                    ),
                ],
            ),
            Hypothesis(
                id="H2",
                statement="The orders-db migration caused the 504s.",
                service="orders-db",
                confidence=0.05,
                status="ruled_out",
                disconfirming_test="Rollback ineffective; DB latency flat.",
                ruled_out_reason="The 14:58 rollback did not resolve the 504s and DB latency stayed flat.",
            ),
        ],
    )


def fake_investigate(
    config: RunConfig,
    tracer: Tracer | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> tuple[InvestigationResult, Ledger]:
    tracer = tracer or Tracer(enabled=False)
    vault = Vault.load(config)
    sc = vault.scenario
    tracer.scenario(vault)
    ledger = Ledger(
        incident_id=f"{config.workspace}-{sc.id}",
        workspace=config.workspace,
        scenario=sc.id,
        query=sc.query,
        as_of=sc.as_of.isoformat(),
        window=[sc.window[0].isoformat(), sc.window[1].isoformat()],
    )

    tracer.phase("hypothesize")
    hyps = _initial_hypotheses()
    ledger.record_hypotheses(hyps)
    tracer.hypotheses(hyps)

    tracer.phase("investigate")
    tool_map = {t.name: t for t in make_tools(vault)}
    for i, (name, args) in enumerate(_STEPS, 1):
        if cancel_check and cancel_check():
            raise InvestigationCancelled()
        tracer.tool_call(i, name, args)
        tool = tool_map.get(name)
        out = str(tool.invoke(args)) if tool else f"(no tool {name})"
        ledger.record_tool(i, name, args, out)
        tracer.tool_result(i, name, out)
        if _DELAY:
            time.sleep(_DELAY)
    tracer.thinking_done(len(_STEPS))

    tracer.phase("adjudicate")
    result = _verdict(sc.query)
    ledger.result = result
    tracer.verdict(result)

    tracer.phase("verify")
    grounding = verify_citations(result, vault)
    ledger.grounding = grounding
    tracer.grounding(grounding.claims_verified, grounding.claims_total)

    return result, ledger
