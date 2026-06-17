"""Run configuration — the object the CLI populates and the engine consumes.

Keeps the engine importable and surface-agnostic: the CLI (and a future API) build a
``RunConfig`` and hand it to ``orchestrator.investigate``.

Workspace location is **config-driven**, not discovered by walking parent directories:
``--workspaces-root`` flag > ``$BIGGY_WORKSPACES_ROOT`` env var (set it in ``.env``) > the
in-repo default. See ``.env.example``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PROVIDER = "google_genai"
DEFAULT_MODEL = "gemini-3.1-flash-lite"
DEFAULT_MAX_STEPS = 12

WORKSPACES_ENV = "BIGGY_WORKSPACES_ROOT"


def default_workspaces_root() -> Path:
    """The in-repo ``workspaces/`` dir, anchored to the package (no CWD search, move-resilient).

    Finds the ``biggy`` package root from this file, then the repo root above ``src/cli/`` — so it
    survives modules moving within the package. Used only when neither ``--workspaces-root`` nor
    ``$BIGGY_WORKSPACES_ROOT`` is set (the common editable-install case). For non-editable installs,
    set ``$BIGGY_WORKSPACES_ROOT``.
    """
    pkg = Path(__file__).resolve()
    while pkg.name != "biggy" and pkg != pkg.parent:
        pkg = pkg.parent
    # pkg == <repo>/src/cli/biggy  ->  repo root is two levels above it.
    return pkg.parents[2] / "workspaces"


def resolve_workspaces_root(override: Path | None = None) -> Path:
    """Resolve the workspaces root from config, in priority order (no directory walking)."""
    if override is not None:
        return Path(override)
    env = os.environ.get(WORKSPACES_ENV)
    if env:
        return Path(env)
    return default_workspaces_root()


@dataclass
class RunConfig:
    """Everything one investigation needs. ``query`` is the user's typed report."""

    query: str
    workspace: str = "acme-checkout"
    scenario: str | None = None
    # Time-frame inputs (raw strings; the engine's resolve_frame turns these into one TimeFrame).
    # Precedence: since+until (range) > as_of/look_back (live) > scenario seed > default now()/2h.
    as_of: str | None = None
    look_back: str | None = None
    since: str | None = None
    until: str | None = None
    provider: str = DEFAULT_PROVIDER
    model: str = DEFAULT_MODEL
    max_steps: int = DEFAULT_MAX_STEPS
    out_dir: Path | None = None
    workspaces_root: Path | None = None
    ablate: list[str] = field(
        default_factory=list
    )  # relpaths hidden from the agent (honesty demo)

    def resolved_workspaces_root(self) -> Path:
        return resolve_workspaces_root(self.workspaces_root)

    @property
    def workspace_dir(self) -> Path:
        return self.resolved_workspaces_root() / self.workspace
