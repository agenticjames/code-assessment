"""The worker's ``TraceSink``: one event -> Redis live stream + Postgres durable row (PHASE2 §1).

``emit`` assigns a monotonic ``seq`` (the total order the UI replays by) and must never throw — a
persistence hiccup must not kill the investigation. Durable write first (so PG replay is complete
even if a browser missed the live stream), then the live fan-out.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any

from biggy.worker import redis_io


class RedisPgSink:
    def __init__(self, redis_conn: Any, db: Any, investigation_id: str) -> None:
        self.r = redis_conn
        self.db = db
        self.id = investigation_id
        self.seq = 0

    def emit(self, event_type: str, data: dict[str, Any]) -> None:
        ts = datetime.now(timezone.utc)
        seq = self.seq
        try:
            self.db.append_trace_event(self.id, seq, ts, event_type, data)
        except Exception as exc:  # noqa: BLE001 - emit must not throw on the hot path
            print(f"[sink] pg append failed (seq={seq}): {exc}", file=sys.stderr)
        try:
            envelope = {
                "seq": seq,
                "ts": ts.isoformat(),
                "type": event_type,
                "data": data,
            }
            redis_io.publish_trace(self.r, self.id, envelope)
        except Exception as exc:  # noqa: BLE001
            print(f"[sink] redis publish failed (seq={seq}): {exc}", file=sys.stderr)
        self.seq += 1
