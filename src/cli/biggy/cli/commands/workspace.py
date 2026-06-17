"""``biggy workspace`` — maintenance commands for a workspace's generated artifacts.

Currently: ``biggy workspace manifest`` (re)writes ``workspaces/<ws>/manifest.json`` — the
agent-safe scenario seeds + corpus profile the web reads. Commit the result; a freshness test
(``tests/test_manifest_fresh.py``) fails if it drifts from the source ``query.yaml`` + telemetry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

app = typer.Typer(
    name="workspace",
    help="Maintain a workspace's generated artifacts (e.g. the public manifest).",
    no_args_is_help=True,
    add_completion=False,
)

_out = Console()
_err = Console(stderr=True)


@app.command("manifest")
def manifest(
    workspace: str = typer.Argument(
        "acme-checkout", help="Workspace whose manifest.json to (re)generate."
    ),
    workspaces_root: Optional[Path] = typer.Option(
        None,
        "--workspaces-root",
        hidden=True,
        help="Override the workspaces/ root (else $BIGGY_WORKSPACES_ROOT or the in-repo default).",
    ),
) -> None:
    """Regenerate the workspace manifest (scenario seeds + corpus profile) the web reads."""
    from biggy.engine.config import resolve_workspaces_root
    from biggy.engine.workspace.manifest import build_manifest

    root = resolve_workspaces_root(workspaces_root) / workspace
    if not root.is_dir():
        _err.print(f"[red]workspace not found:[/] {root}")
        raise typer.Exit(code=2)

    data = build_manifest(root)
    out = root / "manifest.json"
    out.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    n = len(data.get("scenarios", []))
    _out.print(f"wrote {out} [dim]({n} scenarios)[/]")
