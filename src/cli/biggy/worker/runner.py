"""One job's lifecycle (docs/PHASE2.md §1): claim -> run the engine -> persist + stream terminal state."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from biggy.engine.config import RunConfig
from biggy.engine.context import InvestigationCancelled
from biggy.engine.trace import Tracer
from biggy.worker import redis_io
from biggy.worker.contracts import (
    EVENT_CANCELED,
    EVENT_DONE,
    EVENT_ERROR,
    EVENT_STATUS,
    STATUS_CANCELED,
    STATUS_FAILED,
    STATUS_SUCCEEDED,
    Job,
)
from biggy.worker.sink import RedisPgSink


def run_job(job: Job, db: Any, redis_conn: Any) -> None:
    # Lazy import keeps the worker module light and dodges any engine import cycle.
    from biggy.engine.orchestrator import investigate

    sink = RedisPgSink(redis_conn, db, job.id)

    if not db.claim(job.id):
        return  # already claimed or gone — another worker (or a retry) owns it

    sink.emit(EVENT_STATUS, {"state": "running"})
    started = datetime.now(timezone.utc)

    def cancel_check() -> bool:
        return redis_io.is_canceled(redis_conn, job.id)

    config = RunConfig(
        query=job.query,
        workspace=job.workspace,
        scenario=job.scenario,
        as_of=job.as_of,
        look_back=job.look_back,
        since=job.since,
        until=job.until,
        provider=job.provider,
        model=job.model,
        max_steps=job.max_steps,
    )
    try:
        result, ledger = investigate(
            config, tracer=Tracer(sink=sink), cancel_check=cancel_check
        )
        db.finish(job.id, result, ledger, started_at=started)
        sink.emit(EVENT_DONE, {"status": STATUS_SUCCEEDED})
    except InvestigationCancelled:
        db.cancel(job.id)
        sink.emit(EVENT_CANCELED, {})
        sink.emit(EVENT_DONE, {"status": STATUS_CANCELED})
    except Exception as exc:  # noqa: BLE001 - any engine failure becomes a clean failed run
        db.fail(job.id, str(exc))
        sink.emit(EVENT_ERROR, {"message": str(exc)})
        sink.emit(EVENT_DONE, {"status": STATUS_FAILED})
