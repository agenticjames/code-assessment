"""P3 — the worker end-to-end, offline (docs/PHASE2.md §7).

Drives ``run_job`` with the fake investigation against the compose Redis + Postgres: a run persists
(succeeded) and streams a terminal ``done``; a cancel flag yields a canceled run. No LLM. Skipped
unless both services + the applied schema are reachable.
"""

from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest

os.environ.setdefault("BIGGY_FAKE_DELAY", "0")  # no sleeps in tests

DSN = os.environ.get("DATABASE_URL", "postgres://biggy:biggy@localhost:5433/biggy")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6380")


def _ready() -> bool:
    try:
        import psycopg
        import redis

        with psycopg.connect(DSN, connect_timeout=2) as c:
            if not c.execute("SELECT to_regclass('public.investigations')").fetchone()[
                0
            ]:
                return False
        redis.from_url(REDIS_URL).ping()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _ready(), reason="needs compose Postgres+Redis + applied schema"
)


def _setup():
    from biggy.worker import redis_io
    from biggy.worker.db import Db

    return Db.connect(DSN), redis_io.connect(REDIS_URL)


def _stream_types(r, inv_id: str) -> list[str]:
    return [
        json.loads(fields["data"])["type"]
        for _id, fields in r.xrange(f"trace:{inv_id}")
    ]


def test_fake_run_succeeds_and_streams() -> None:
    from biggy.worker.contracts import Job
    from biggy.worker.fake import fake_investigate
    from biggy.worker.runner import run_job

    db, r = _setup()
    job = Job(id=str(uuid4()), query="checkout is throwing 504s", scenario="A")
    try:
        db.create_queued(job)
        run_job(job, db, r, investigate_fn=fake_investigate)

        status, outcome, top = db.conn.execute(
            "SELECT status, outcome, top_service FROM investigations WHERE id=%s",
            (job.id,),
        ).fetchone()
        assert status == "succeeded"
        assert outcome == "root_cause"
        assert top == "rate-limiter"

        types = _stream_types(r, job.id)
        assert "status" in types
        assert "verdict" in types
        assert "grounding" in types
        assert types[-1] == "done"

        def _count(table: str) -> int:
            return db.conn.execute(
                f"SELECT count(*) FROM {table} WHERE investigation_id=%s", (job.id,)
            ).fetchone()[0]

        assert _count("tool_calls") >= 1
        assert _count("citations") >= 1
    finally:
        db.conn.execute("DELETE FROM investigations WHERE id=%s", (job.id,))
        r.delete(f"trace:{job.id}")
        db.close()


def test_cancel_flag_yields_canceled() -> None:
    from biggy.worker import redis_io
    from biggy.worker.contracts import Job
    from biggy.worker.fake import fake_investigate
    from biggy.worker.runner import run_job

    db, r = _setup()
    job = Job(id=str(uuid4()), query="checkout 504s", scenario="A")
    try:
        db.create_queued(job)
        redis_io.request_cancel(r, job.id)  # cancel BEFORE running
        run_job(job, db, r, investigate_fn=fake_investigate)

        status = db.conn.execute(
            "SELECT status FROM investigations WHERE id=%s", (job.id,)
        ).fetchone()[0]
        assert status == "canceled"
        assert _stream_types(r, job.id)[-1] == "done"
    finally:
        db.conn.execute("DELETE FROM investigations WHERE id=%s", (job.id,))
        r.delete(f"trace:{job.id}")
        r.delete(f"cancel:{job.id}")
        db.close()
