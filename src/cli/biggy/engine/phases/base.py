"""The phase contract.

A ``Phase`` is anything with a ``name`` and a ``run(inv)`` that mutates the shared ``Investigation``.
The protocol is deliberately not LLM-shaped — the Inc-2 ``verify`` phase will satisfy it with pure
deterministic code. Each phase maps cleanly to a future LangGraph node.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from biggy.engine.context import Investigation

_PROMPTS = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a versioned phase prompt from ``engine/prompts/<name>.md``."""
    return (_PROMPTS / f"{name}.md").read_text(encoding="utf-8")


@runtime_checkable
class Phase(Protocol):
    name: str

    def run(self, inv: "Investigation") -> None: ...
