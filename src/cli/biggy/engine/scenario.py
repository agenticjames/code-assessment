"""Scenario directory access — the two halves ``--scenario`` provides, behind one door.

A scenario is a directory under ``<workspace>/scenarios/`` holding:

- ``query.yaml`` — the **frame seed** (agent-safe): the canned report + the time frame
  (``as_of`` + ``look_back`` for a live incident, or a ``range`` for a retrospective).
- ``HIDDEN_TRUTH.md`` — the **answer key** (grader-only): never surfaced to the agent.

This module is the single reader of that directory, so the three consumers stay DRY:
``engine/frame.py`` seeds a :class:`~biggy.engine.frame.TimeFrame` from a scenario,
``engine/workspace/manifest.py`` lists the agent-safe seeds for the web, and the grader
(``eval``) resolves the answer-key path. The time concept itself lives in ``frame.py``; this
module only *locates and parses* — it does not compute windows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from biggy.engine.evidence.timeutil import parse_iso

DEFAULT_LOOK_BACK = "2h"


@dataclass(frozen=True)
class ScenarioSeed:
    """The agent-safe metadata in a scenario's ``query.yaml`` (never the answer key).

    ``mode`` is ``"live"`` (paged mid-incident — ``as_of`` + ``look_back``) or
    ``"retrospective"`` (a closed past ``range``). Exactly one of ``look_back`` / ``range`` is set.
    """

    id: str
    slug: str
    label: str
    query: str
    severity: str | None
    mode: str
    as_of: datetime
    look_back: str | None
    range: tuple[datetime, datetime] | None


def find_dir(workspace_dir: Path, scenario_id: str) -> Path | None:
    """The scenario directory matching an id (``"A"``) or full name (``"A-checkout-504"``)."""
    sdir = workspace_dir / "scenarios"
    if not sdir.is_dir():
        return None
    return next(
        (
            d
            for d in sorted(sdir.iterdir())
            if d.is_dir()
            and (d.name == scenario_id or d.name.split("-")[0] == scenario_id)
        ),
        None,
    )


def read_seed(workspace_dir: Path, scenario_id: str) -> ScenarioSeed:
    """Parse a scenario's frame seed. Raises ``FileNotFoundError`` if the scenario is unknown."""
    d = find_dir(workspace_dir, scenario_id)
    if d is None:
        raise FileNotFoundError(
            f"scenario {scenario_id!r} not found under {workspace_dir / 'scenarios'}"
        )
    return _seed_from_dir(d)


def hidden_truth_path(workspace_dir: Path, scenario_id: str) -> Path | None:
    """The answer-key path for a scenario, or ``None`` if it has none / is unknown (grader-only)."""
    d = find_dir(workspace_dir, scenario_id)
    if d is None:
        return None
    ht = d / "HIDDEN_TRUTH.md"
    return ht if ht.exists() else None


def iter_seeds(workspace_dir: Path) -> list[ScenarioSeed]:
    """Every scenario's frame seed, sorted by directory name (the manifest's source order)."""
    sdir = workspace_dir / "scenarios"
    if not sdir.is_dir():
        return []
    return [
        _seed_from_dir(d)
        for d in sorted(sdir.iterdir())
        if d.is_dir() and (d / "query.yaml").is_file()
    ]


def _seed_from_dir(d: Path) -> ScenarioSeed:
    frame = yaml.safe_load((d / "query.yaml").read_text(encoding="utf-8")) or {}
    rng = frame.get("range")
    range_t = (parse_iso(str(rng["from"])), parse_iso(str(rng["to"]))) if rng else None
    # A ``range`` is authoritative for the mode — a closed past window is retrospective.
    mode = "retrospective" if range_t else str(frame.get("mode", "live"))
    parts = d.name.split("-")
    slug = str(frame.get("slug") or ("-".join(parts[1:]) or d.name))
    return ScenarioSeed(
        id=str(frame.get("id", parts[0])),
        slug=slug,
        label=str(frame.get("label") or slug),
        query=str(frame.get("query", "")),
        severity=frame.get("severity"),
        mode=mode,
        as_of=parse_iso(str(frame["as_of"])),
        look_back=None if range_t else str(frame.get("look_back", DEFAULT_LOOK_BACK)),
        range=range_t,
    )
