"""The incident **time frame** — the single concept "what slice of time are we investigating".

This is the value object that replaces ``--scenario``'s old double duty. A scenario now merely
*seeds* a frame; the frame can equally come from explicit flags (``--as-of`` / ``--look-back`` or
``--since`` / ``--until``) or default to "now, last 2h".

:func:`resolve_frame` is the **only** place a window is computed — in the engine, because only the
engine knows "now" and how telemetry is clamped. The web mirrors the trivial ``as_of − look_back``
arithmetic in ``lib/timeframe.ts`` for an at-rest preview, but the authoritative frame is always the
one this resolver produces.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal

from biggy.engine import scenario
from biggy.engine.evidence.timeutil import parse_iso, parse_lookback

if TYPE_CHECKING:
    from biggy.engine.config import RunConfig

DEFAULT_LOOK_BACK = "2h"
Mode = Literal["live", "retrospective"]


def now() -> datetime:
    """The investigation "now" (aware UTC). One seam so tests can pin it."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class TimeFrame:
    """An incident window + its clamp. ``window`` is always ``(start, end)`` with ``end == as_of``.

    ``live`` — paged mid-incident: ``window = [as_of − look_back, as_of]``; nothing after ``as_of``
    is visible (no hindsight). ``retrospective`` — a closed past range: ``window = [since, until]``,
    ``as_of = until`` (the range is historical, so the clamp sits at its end).
    """

    as_of: datetime
    window: tuple[datetime, datetime]
    mode: Mode
    look_back: str | None = None

    @property
    def start(self) -> datetime:
        return self.window[0]

    @property
    def end(self) -> datetime:
        return self.window[1]

    def label(self) -> str:
        """Compact display span — ``2026-06-16T13:15–15:15Z`` within a day, both dates across days."""
        s, e = self.window
        if s.date() == e.date():
            return f"{s:%Y-%m-%dT%H:%M}–{e:%H:%M}Z"
        return f"{s:%Y-%m-%dT%H:%M}–{e:%Y-%m-%dT%H:%M}Z"

    @classmethod
    def live(cls, as_of: datetime, look_back: str) -> "TimeFrame":
        return cls(
            as_of=as_of,
            window=(as_of - parse_lookback(look_back), as_of),
            mode="live",
            look_back=look_back,
        )

    @classmethod
    def retrospective(cls, since: datetime, until: datetime) -> "TimeFrame":
        if until < since:
            raise ValueError(f"range end {until} precedes start {since}")
        return cls(as_of=until, window=(since, until), mode="retrospective")


def resolve_frame(config: "RunConfig") -> TimeFrame:
    """Resolve the one authoritative :class:`TimeFrame` from a run config. Precedence ladder:

    1. explicit range (``since`` + ``until``) → retrospective
    2. explicit ``as_of`` and/or ``look_back`` → live (``as_of`` defaults to ``now()``)
    3. a ``scenario`` seed → its frame (live or retrospective, from its ``query.yaml``)
    4. nothing → live default ``now()`` / ``2h``
    """
    if config.since or config.until:
        if not (config.since and config.until):
            raise ValueError("--since and --until must be given together")
        return TimeFrame.retrospective(parse_iso(config.since), parse_iso(config.until))

    if config.as_of or config.look_back:
        as_of = parse_iso(config.as_of) if config.as_of else now()
        return TimeFrame.live(as_of, config.look_back or DEFAULT_LOOK_BACK)

    if config.scenario:
        return _frame_from_scenario(config)

    return TimeFrame.live(now(), DEFAULT_LOOK_BACK)


def _frame_from_scenario(config: "RunConfig") -> TimeFrame:
    seed = scenario.read_seed(config.workspace_dir, config.scenario or "")
    if seed.range is not None:
        return TimeFrame.retrospective(*seed.range)
    return TimeFrame.live(seed.as_of, seed.look_back or DEFAULT_LOOK_BACK)
