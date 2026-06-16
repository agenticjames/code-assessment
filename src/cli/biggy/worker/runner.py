"""One job's lifecycle (docs/PHASE2.md §1): claim -> run the engine -> persist + stream terminal state.

``investigate_fn`` is injectable: the real ``orchestrator.investigate`` in production, the fake in
tests and in ``BIGGY_FAKE_RUN`` demo mode. The interface is ``fn(config, tracer, cancel_check)``.
"""

from __future__ import annotations

from collections.abc import Callable
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


def _default_investigate(
    config: RunConfig, tracer: Tracer, cancel_check: Callable[[], bool]
):
    # Wrapper so cancel_check lands on the right keyword (orchestrator's 3rd positional is `pipeline`).
    from biggy.engine.orchestrator import investigate

    return investigate(config, tracer=tracer, cancel_check=cancel_check)


def run_job(
    job: Job,
    db: Any,
    redis_conn: Any,
    *,
    investigate_fn: Callable[..., Any] | None = None,
) -> None:
    investigate_fn = investigate_fn or _default_investigate
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
        provider=job.provider,
        model=job.model,
        max_steps=job.max_steps,
    )
    try:
        result, ledger = investigate_fn(config, Tracer(sink=sink), cancel_check)
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
