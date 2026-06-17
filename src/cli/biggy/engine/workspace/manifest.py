"""Build the public **workspace manifest** — agent-safe scenario seeds + corpus profile.

The web cannot read ``scenarios/`` (its access boundary denies it) and must not re-implement the
engine's telemetry timestamp parsing. So the engine emits one committed artifact,
``workspaces/<ws>/manifest.json``, that the web consumes for two things:

- the scenario **presets** (id / label / query / frame seed) — killing the hand-duplicated list
  that used to live in ``web/lib/scenarios.ts``;
- the **timeline** corpus bounds + signal density.

The manifest is deliberately answer-key-free: it carries each scenario's *frame* (when to look),
never its ``HIDDEN_TRUTH``. A freshness test regenerates it and fails on drift.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from biggy.engine.evidence.timeutil import extract_timestamp
from biggy.engine.scenario import ScenarioSeed, iter_seeds

DENSITY_BUCKETS = 60


def build_manifest(workspace_dir: Path) -> dict:
    """The full manifest dict for one workspace (deterministic — safe to diff against the commit)."""
    ws = (
        yaml.safe_load((workspace_dir / "workspace.yaml").read_text(encoding="utf-8"))
        or {}
    )
    return {
        "workspace": str(ws.get("name", workspace_dir.name)),
        "scenarios": [_scenario_entry(s) for s in iter_seeds(workspace_dir)],
        "corpus": _corpus_profile(workspace_dir),
    }


def _scenario_entry(seed: ScenarioSeed) -> dict:
    entry: dict = {
        "id": seed.id,
        "label": seed.label,
        "query": seed.query,
        "mode": seed.mode,
    }
    if seed.range is not None:
        entry["range"] = {
            "from": seed.range[0].isoformat(),
            "to": seed.range[1].isoformat(),
        }
    else:
        entry["as_of"] = seed.as_of.isoformat()
        entry["look_back"] = seed.look_back
    return entry


def _corpus_profile(workspace_dir: Path) -> dict:
    """Min/max timestamp across the telemetry corpus + a fixed-bucket signal-density histogram.

    Reuses the engine's :func:`extract_timestamp`, so the web never parses telemetry itself. Lines
    without a timestamp (CSV headers, stack-trace frames, chat time-only lines) are simply skipped.
    """
    stamps = sorted(_telemetry_timestamps(workspace_dir))
    if not stamps:
        return {"min": None, "max": None, "buckets": DENSITY_BUCKETS, "density": []}
    lo, hi = stamps[0], stamps[-1]
    span = (hi - lo).total_seconds()
    density = [0] * DENSITY_BUCKETS
    for ts in stamps:
        frac = (ts - lo).total_seconds() / span if span else 0.0
        idx = min(int(frac * DENSITY_BUCKETS), DENSITY_BUCKETS - 1)
        density[idx] += 1
    return {
        "min": lo.isoformat(),
        "max": hi.isoformat(),
        "buckets": DENSITY_BUCKETS,
        "density": density,
    }


def _telemetry_timestamps(workspace_dir: Path) -> list[datetime]:
    tdir = workspace_dir / "telemetry"
    out: list[datetime] = []
    for path in sorted(tdir.rglob("*")) if tdir.is_dir() else []:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            ts = extract_timestamp(line)
            if ts is not None:
                out.append(ts)
    return out
