"""Timestamp parsing for the telemetry corpus (all UTC).

The corpus mixes three on-disk timestamp shapes; the engine normalises them to
aware UTC ``datetime`` so evidence can be sliced to an incident window:

- ISO-8601 ``2026-06-16T14:47:00Z`` (logfmt logs, CSV, JSONL, deploys, postgres uses a space)
- redis native ``08 Jun 2026 03:02:11.004``
- postgres native ``2026-06-08 03:11:02.114 UTC`` (matched by the ISO branch's space form)
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_ISO = re.compile(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})")
_REDIS = re.compile(r"\b(\d{2}) ([A-Z][a-z]{2}) (\d{4}) (\d{2}):(\d{2}):(\d{2})")
_MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ],
        start=1,
    )
}


def parse_iso(s: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp (e.g. ``2026-06-16T15:15:00Z``) to aware UTC."""
    dt = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_lookback(s: str) -> timedelta:
    """Parse a look-back string like ``2h`` / ``90m`` / ``1d`` into a timedelta."""
    m = re.fullmatch(r"(\d+)\s*([smhd])", s.strip().lower())
    if not m:
        raise ValueError(f"bad look_back: {s!r} (expected e.g. '2h', '90m', '1d')")
    return timedelta(
        seconds=int(m.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]
    )


def extract_timestamp(line: str) -> datetime | None:
    """Best-effort: pull a UTC datetime out of one telemetry line, or None if it has none.

    None signals a continuation line (e.g. an indented stack-trace frame) or a structural
    line (a YAML/CSV header) — the caller decides how to treat those.
    """
    m = _REDIS.search(line)
    if m and m.group(2) in _MONTHS:
        day, mon, year, hh, mm, ss = m.groups()
        return datetime(
            int(year),
            _MONTHS[mon],
            int(day),
            int(hh),
            int(mm),
            int(ss),
            tzinfo=timezone.utc,
        )
    m = _ISO.search(line)
    if m:
        return parse_iso(f"{m.group(1)}T{m.group(2)}")
    return None
