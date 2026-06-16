"""Shared test fixtures.

Offline tests (vault/tools/CLI plumbing) need no LLM. The end-to-end engine test makes a REAL
Gemini call and is skipped automatically when no API key is present, so keyless CI stays green.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import find_dotenv, load_dotenv

from biggy.engine.config import RunConfig
from biggy.engine.llm.client import ensure_google_key

load_dotenv(find_dotenv(usecwd=True))
ensure_google_key()
_HAS_KEY = bool(os.environ.get("GOOGLE_API_KEY"))

# src/cli/tests/conftest.py -> parents[3] is the repo root holding workspaces/.
REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACES = REPO_ROOT / "workspaces"


@pytest.fixture
def ws_root() -> Path:
    return WORKSPACES


@pytest.fixture
def config_a(ws_root: Path) -> RunConfig:
    """Scenario A (real provider). Used offline by vault/tools tests (which make no LLM call)."""
    return RunConfig(
        query="checkout is throwing 504s and customers are complaining",
        workspace="acme-checkout",
        scenario="A",
        workspaces_root=ws_root,
    )


@pytest.fixture
def needs_llm() -> None:
    """Skip the test unless a Gemini API key is available (live integration)."""
    if not _HAS_KEY:
        pytest.skip("needs GEMINI_API_KEY / GOOGLE_API_KEY for a live Gemini call")
