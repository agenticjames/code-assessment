"""P2 — the worker's Postgres writer (docs/PHASE2.md §7).

Round-trips a fake run against the compose Postgres: create_queued -> claim (idempotent) -> trace
event -> tool call -> finish (verdict + ledger + citations + denormalized columns) -> fail. Skipped
unless the compose Postgres is reachable AND the Drizzle schema has been applied (`pnpm db:push`).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

DSN = os.environ.get("DATABASE_URL", "postgres://biggy:biggy@localhost:5433/biggy")


def _schema_ready() -> bool:
    try:
        import psycopg

        with psycopg.connect(DSN, connect_timeout=2) as c:
            row = c.execute("SELECT to_regclass('public.investigations')").fetchone()
            return bool(row and row[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _schema_ready(),
    reason="needs compose Postgres + applied schema (docker compose up && pnpm db:push)",
)


def _fake_result_and_ledger(query: str):
    from biggy.engine.ledger import Ledger, ToolCall
    from biggy.engine.schemas import (
        EvidenceRef,
        Grounding,
        Hypothesis,
        InvestigationResult,
    )

    result = InvestigationResult(
        query=query,
        outcome="root_cause",
        summary="the rate-limiter change exhausted the shared Redis pool",
        recommended_action="roll back dep-7e2a",
        hypotheses=[
            Hypothesis(
                id="H1",
                statement="rate-limiter config change exhausted the pool",
                service="rate-limiter",
                confidence=0.82,
                status="confirmed",
                supporting=[
                    EvidenceRef(
                        claim="max_tokens cut 100 -> 10",
                        snippet="max_tokens: 10",
                        source="telemetry/changes/dep-7e2a.diff:9",
                        verified=True,
                    )
                ],
            )
        ],
    )
    ledger = Ledger(
        incident_id="acme-checkout-A",
        workspace="acme-checkout",
        scenario="A",
        query=query,
        tool_calls=[
            ToolCall(step=1, name="list_evidence", args={}, result_preview="...")
        ],
        result=result,
        grounding=Grounding(claims_total=1, claims_verified=1),
    )
    return result, ledger


def test_worker_db_round_trip() -> None:
    from biggy.worker.contracts import Job
    from biggy.worker.db import Db

    db = Db.connect(DSN)
    job = Job(id=str(uuid4()), query="checkout is throwing 504s", scenario="A")
    try:
        db.create_queued(job)
        assert db.claim(job.id) is True
        assert db.claim(job.id) is False  # idempotent: not claimable twice

        db.append_trace_event(
            job.id, 0, datetime.now(timezone.utc), "status", {"state": "running"}
        )

        result, ledger = _fake_result_and_ledger(job.query)
        db.finish(job.id, result, ledger, started_at=datetime.now(timezone.utc))

        row = db.conn.execute(
            "SELECT status, outcome, top_service, grounding_verified, grounding_total, "
            "step_count, recommended_action FROM investigations WHERE id=%s",
            (job.id,),
        ).fetchone()
        assert row is not None
        assert row[0] == "succeeded"
        assert row[1] == "root_cause"
        assert row[2] == "rate-limiter"
        assert (row[3], row[4]) == (1, 1)
        assert row[5] == 1
        assert row[6] and "dep-7e2a" in row[6]

        def _count(table: str) -> int:
            return db.conn.execute(
                f"SELECT count(*) FROM {table} WHERE investigation_id=%s", (job.id,)
            ).fetchone()[0]

        assert _count("tool_calls") == 1
        assert _count("trace_events") == 1
        assert _count("citations") == 1

        db.fail(job.id, "boom")  # exercise the failure path
        status = db.conn.execute(
            "SELECT status, error FROM investigations WHERE id=%s", (job.id,)
        ).fetchone()
        assert status[0] == "failed" and status[1] == "boom"
    finally:
        db.conn.execute("DELETE FROM investigations WHERE id=%s", (job.id,))
        db.close()
