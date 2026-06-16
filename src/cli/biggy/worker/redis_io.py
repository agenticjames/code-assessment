"""Redis I/O for the worker (docs/PHASE2.md §4.5).

The queue (a Redis Stream + consumer group) and the live trace fan-out. Plain redis-py; the worker
is the only consumer. Next produces jobs with ``XADD biggy:jobs * data <json>`` and tails the
``trace:{id}`` streams the sink writes here.
"""

from __future__ import annotations

import json
from typing import Any

import redis

JOBS_STREAM = "biggy:jobs"
GROUP = "workers"
TRACE_TTL_SECONDS = 24 * 3600
TRACE_MAXLEN = 1000


def connect(url: str) -> redis.Redis:
    # socket_timeout=None so a blocking XREADGROUP waits for the server's BLOCK to return.
    return redis.from_url(
        url, decode_responses=True, socket_timeout=None, socket_keepalive=True
    )


def ensure_group(r: redis.Redis) -> None:
    """Create the consumer group (and the stream) if absent; ignore if it already exists."""
    try:
        r.xgroup_create(JOBS_STREAM, GROUP, id="0", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def claim_job(
    r: redis.Redis, consumer: str, block_ms: int = 2000
) -> tuple[str, dict[str, str]] | None:
    """Block (up to ``block_ms``) for the next undelivered job. Returns ``(msg_id, fields)`` or None."""
    try:
        resp = r.xreadgroup(
            GROUP, consumer, {JOBS_STREAM: ">"}, count=1, block=block_ms
        )
    except redis.exceptions.TimeoutError:
        return None  # no job this cycle — the loop retries
    if not resp:
        return None
    _stream, messages = resp[0]
    if not messages:
        return None
    msg_id, fields = messages[0]
    return msg_id, fields


def ack(r: redis.Redis, msg_id: str) -> None:
    r.xack(JOBS_STREAM, GROUP, msg_id)


def enqueue(r: redis.Redis, job_json: str) -> str:
    """Add a job (a JSON string) to the queue. Mirrors Next's XADD; used by tests + a CLI helper."""
    return r.xadd(JOBS_STREAM, {"data": job_json})


def publish_trace(
    r: redis.Redis, investigation_id: str, envelope: dict[str, Any]
) -> None:
    key = f"trace:{investigation_id}"
    r.xadd(key, {"data": json.dumps(envelope)}, maxlen=TRACE_MAXLEN, approximate=True)
    r.expire(key, TRACE_TTL_SECONDS)


def request_cancel(r: redis.Redis, investigation_id: str) -> None:
    r.set(f"cancel:{investigation_id}", "1", ex=3600)


def is_canceled(r: redis.Redis, investigation_id: str) -> bool:
    return bool(r.exists(f"cancel:{investigation_id}"))
