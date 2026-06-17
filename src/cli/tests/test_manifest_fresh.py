"""The committed workspace manifest must match a fresh regeneration (no drift), and must never
leak the answer key. This is the CI freshness guard for ``workspaces/<ws>/manifest.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

from biggy.engine.workspace.manifest import build_manifest

REPO_ROOT = Path(__file__).resolve().parents[3]
WS = REPO_ROOT / "workspaces" / "acme-checkout"

_SEED_KEYS = {"id", "label", "query", "mode", "as_of", "look_back", "range"}


def test_manifest_matches_source() -> None:
    committed = json.loads((WS / "manifest.json").read_text(encoding="utf-8"))
    fresh = build_manifest(WS)
    assert fresh == committed, (
        "workspaces/acme-checkout/manifest.json is stale — run "
        "`biggy workspace manifest acme-checkout` and commit the result."
    )


def test_manifest_is_answer_key_free() -> None:
    committed = json.loads((WS / "manifest.json").read_text(encoding="utf-8"))
    assert "HIDDEN_TRUTH" not in json.dumps(committed)
    for s in committed["scenarios"]:
        leaked = set(s) - _SEED_KEYS
        assert not leaked, f"scenario {s.get('id')} leaks non-seed keys: {leaked}"
