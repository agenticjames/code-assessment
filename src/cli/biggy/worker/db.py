"""Postgres writer for the worker (docs/PHASE2.md §4.3).

The durable system of record. Drizzle (``src/web/lib/db/schema.ts``) OWNS the schema + migrations;
this module only *writes rows*. Plain psycopg + SQL (no ORM): the worker's needs are a handful of
typed statements, and keeping a single schema owner (Drizzle) avoids a second migration source.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import psycopg
from psycopg.types.json import Jsonb

from biggy.worker.contracts import (
    STATUS_CANCELED,
    STATUS_FAILED,
    STATUS_RUNNING,
    STATUS_SUCCEEDED,
)

if TYPE_CHECKING:
    from biggy.engine.ledger import Ledger
    from biggy.engine.schemas import InvestigationResult
    from biggy.worker.contracts import Job


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Db:
    """Thin psycopg writer. One autocommit connection; statements are small and independent."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    @classmethod
    def connect(cls, dsn: str) -> "Db":
        return cls(psycopg.connect(dsn, autocommit=True))

    def close(self) -> None:
        self.conn.close()

    # ---- lifecycle ----
    def create_queued(self, job: "Job") -> None:
        """Insert a queued row. Normally Next does this; used by the worker's tests + fake CLI."""
        self.conn.execute(
            "INSERT INTO investigations "
            "(id, status, workspace, scenario, query, provider, model, max_steps) "
            "VALUES (%s, 'queued', %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
            (
                job.id,
                job.workspace,
                job.scenario,
                job.query,
                job.provider,
                job.model,
                job.max_steps,
            ),
        )

    def claim(self, investigation_id: str) -> bool:
        """Atomically move queued -> running. False if not claimable (already taken/gone)."""
        now = _utcnow()
        cur = self.conn.execute(
            "UPDATE investigations SET status=%s, started_at=%s, updated_at=%s "
            "WHERE id=%s AND status='queued'",
            (STATUS_RUNNING, now, now, investigation_id),
        )
        return cur.rowcount == 1

    def append_trace_event(
        self, investigation_id: str, seq: int, ts: datetime, type_: str, payload: dict
    ) -> None:
        self.conn.execute(
            "INSERT INTO trace_events (investigation_id, seq, ts, type, payload) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (investigation_id, seq) DO NOTHING",
            (investigation_id, seq, ts, type_, Jsonb(payload)),
        )

    def add_tool_call(
        self, investigation_id: str, step: int, name: str, args: dict, preview: str
    ) -> None:
        self.conn.execute(
            "INSERT INTO tool_calls (investigation_id, step, name, args, result_preview) "
            "VALUES (%s, %s, %s, %s, %s)",
            (investigation_id, step, name, Jsonb(args or {}), preview),
        )

    # ---- terminal states ----
    def finish(
        self,
        investigation_id: str,
        result: "InvestigationResult",
        ledger: "Ledger",
        started_at: datetime | None = None,
    ) -> None:
        """Persist the verdict + ledger + denormalized columns; insert citations; mark succeeded."""
        g = ledger.grounding
        ranked = (
            sorted(result.hypotheses, key=lambda h: -h.confidence)
            if result.hypotheses
            else []
        )
        top = ranked[0] if ranked else None
        now = _utcnow()
        duration = (
            int((now - started_at).total_seconds() * 1000) if started_at else None
        )
        # The authoritative resolved frame (engine-computed) lands here — overwriting any preview
        # the web seeded at queue time. ledger.as_of / .window are ISO-8601 strings.
        win = ledger.window or []
        fr_as_of = datetime.fromisoformat(ledger.as_of) if ledger.as_of else None
        win_start = datetime.fromisoformat(win[0]) if len(win) > 0 else None
        win_end = datetime.fromisoformat(win[1]) if len(win) > 1 else None
        self.conn.execute(
            "UPDATE investigations SET "
            "status=%s, finished_at=%s, updated_at=%s, duration_ms=%s, step_count=%s, "
            "as_of=%s, window_start=%s, window_end=%s, "
            "outcome=%s, summary=%s, top_service=%s, top_confidence=%s, "
            "grounding_verified=%s, grounding_total=%s, recommended_action=%s, "
            "result_json=%s, ledger_json=%s, error=NULL WHERE id=%s",
            (
                STATUS_SUCCEEDED,
                now,
                now,
                duration,
                len(ledger.tool_calls),
                fr_as_of,
                win_start,
                win_end,
                result.outcome,
                result.summary,
                top.service if top else None,
                top.confidence if top else None,
                g.claims_verified if g else None,
                g.claims_total if g else None,
                result.recommended_action,
                Jsonb(result.model_dump()),
                Jsonb(ledger.model_dump()),
                investigation_id,
            ),
        )
        self._insert_tool_calls(investigation_id, ledger)
        self._insert_citations(investigation_id, result)

    def _insert_tool_calls(self, investigation_id: str, ledger: "Ledger") -> None:
        for tc in ledger.tool_calls:
            self.add_tool_call(
                investigation_id, tc.step, tc.name, tc.args, tc.result_preview
            )

    def _insert_citations(
        self, investigation_id: str, result: "InvestigationResult"
    ) -> None:
        for h in result.hypotheses:
            for stance, refs in (
                ("support", h.supporting),
                ("refute", h.contradicting),
            ):
                for e in refs:
                    path, _, line = e.source.partition(":")
                    self.conn.execute(
                        "INSERT INTO citations (investigation_id, hypothesis_id, stance, "
                        "claim, snippet, source_path, source_line, verified) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (
                            investigation_id,
                            h.id,
                            stance,
                            e.claim,
                            e.snippet,
                            path,
                            int(line) if line.isdigit() else None,
                            e.verified,
                        ),
                    )

    def fail(self, investigation_id: str, message: str) -> None:
        now = _utcnow()
        self.conn.execute(
            "UPDATE investigations SET status=%s, finished_at=%s, updated_at=%s, error=%s "
            "WHERE id=%s",
            (STATUS_FAILED, now, now, message[:2000], investigation_id),
        )

    def cancel(self, investigation_id: str) -> None:
        now = _utcnow()
        self.conn.execute(
            "UPDATE investigations SET status=%s, finished_at=%s, updated_at=%s WHERE id=%s",
            (STATUS_CANCELED, now, now, investigation_id),
        )
