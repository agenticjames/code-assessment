"""``resolve_frame`` — the single time-frame precedence ladder (engine/frame.py). All offline.

Ladder: explicit range (since+until) > explicit live (as_of/look_back) > scenario seed > default.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from biggy.engine import frame as frame_mod
from biggy.engine.config import RunConfig
from biggy.engine.frame import TimeFrame, resolve_frame

UTC = timezone.utc
PINNED = datetime(2026, 6, 16, 15, 15, tzinfo=UTC)


@pytest.fixture
def pinned_now(monkeypatch):
    """Pin ``now()`` so the default/look-back-only rungs are deterministic."""
    monkeypatch.setattr(frame_mod, "now", lambda: PINNED)
    return PINNED


def _cfg(**kw) -> RunConfig:
    return RunConfig(query="x", workspace="acme-checkout", **kw)


# ---- rung 4: default ----
def test_default_is_now_minus_2h(pinned_now):
    f = resolve_frame(_cfg())
    assert f.mode == "live"
    assert f.as_of == PINNED
    assert f.window == (PINNED - timedelta(hours=2), PINNED)
    assert f.look_back == "2h"


# ---- rung 2: explicit live ----
def test_explicit_as_of_and_look_back():
    f = resolve_frame(_cfg(as_of="2026-06-16T15:15:00Z", look_back="30m"))
    assert f.mode == "live"
    assert f.as_of == PINNED
    assert f.window[0] == PINNED - timedelta(minutes=30)


def test_look_back_only_defaults_as_of_to_now(pinned_now):
    f = resolve_frame(_cfg(look_back="1h"))
    assert f.as_of == PINNED
    assert f.window[0] == PINNED - timedelta(hours=1)


# ---- rung 1: explicit range ----
def test_explicit_range_is_retrospective():
    f = resolve_frame(_cfg(since="2026-06-10T00:00:00Z", until="2026-06-12T23:59:59Z"))
    assert f.mode == "retrospective"
    assert f.window == (
        datetime(2026, 6, 10, tzinfo=UTC),
        datetime(2026, 6, 12, 23, 59, 59, tzinfo=UTC),
    )
    assert f.as_of == f.window[1]
    assert f.look_back is None


def test_half_a_range_raises():
    with pytest.raises(ValueError):
        resolve_frame(_cfg(since="2026-06-10T00:00:00Z"))


# ---- rung 3: scenario seed ----
def test_scenario_seed_live(ws_root):
    f = resolve_frame(_cfg(scenario="A", workspaces_root=ws_root))
    assert f.mode == "live"
    assert f.as_of == PINNED
    assert f.window[0] == datetime(2026, 6, 16, 13, 15, tzinfo=UTC)


def test_scenario_seed_retrospective_G(ws_root):
    f = resolve_frame(_cfg(scenario="G", workspaces_root=ws_root))
    assert f.mode == "retrospective"
    assert f.window == (
        datetime(2026, 6, 10, tzinfo=UTC),
        datetime(2026, 6, 12, 23, 59, 59, tzinfo=UTC),
    )


def test_unknown_scenario_raises(ws_root):
    with pytest.raises(FileNotFoundError):
        resolve_frame(_cfg(scenario="ZZZ", workspaces_root=ws_root))


# ---- precedence: explicit flags beat a scenario seed ----
def test_explicit_flags_override_scenario(pinned_now, ws_root):
    f = resolve_frame(_cfg(scenario="A", look_back="15m", workspaces_root=ws_root))
    assert (
        f.as_of == PINNED
    )  # now(), not A's 15:15 — the explicit-live rung fires first
    assert f.window[0] == PINNED - timedelta(minutes=15)


# ---- TimeFrame helpers ----
def test_timeframe_label_and_accessors():
    f = TimeFrame.live(PINNED, "2h")
    assert f.start == PINNED - timedelta(hours=2)
    assert f.end == PINNED
    assert f.label() == "2026-06-16T13:15–15:15Z"


def test_retrospective_rejects_inverted_range():
    with pytest.raises(ValueError):
        TimeFrame.retrospective(
            datetime(2026, 6, 12, tzinfo=UTC), datetime(2026, 6, 10, tzinfo=UTC)
        )
