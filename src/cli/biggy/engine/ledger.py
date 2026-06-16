"""The Investigation Ledger — the engine's evolving, serialisable state (the blackboard).

It records the initial hypothesis set (post-hypothesize), the tool calls made while testing, and
the adjudicated verdict — so ``ledger.json`` shows the hypotheses evolving open -> confirmed/ruled_out.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from biggy.engine.schemas import Grounding, Hypothesis, InvestigationResult


class ToolCall(BaseModel):
    step: int
    name: str
    args: dict = Field(default_factory=dict)
    result_preview: str = ""


class Ledger(BaseModel):
    incident_id: str
    workspace: str
    scenario: str | None = None
    query: str
    as_of: str | None = None
    window: list[str] = Field(default_factory=list)
    initial_hypotheses: list[Hypothesis] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    result: InvestigationResult | None = None
    grounding: Grounding | None = (
        None  # set by the verify phase (deterministic citation check)
    )

    def record_hypotheses(self, hypotheses: list[Hypothesis]) -> None:
        """Snapshot the candidate set right after the hypothesize phase."""
        self.initial_hypotheses = hypotheses

    def record_tool(self, step: int, name: str, args: dict, result: str) -> None:
        preview = result if len(result) <= 280 else result[:277] + "..."
        self.tool_calls.append(
            ToolCall(step=step, name=name, args=args or {}, result_preview=preview)
        )

    def citations(self) -> list[str]:
        """Every citation source in the verdict's evidence (supporting + contradicting)."""
        if not self.result:
            return []
        return [
            e.source
            for h in self.result.hypotheses
            for e in (h.supporting + h.contradicting)
        ]

    def to_json(self, path: Path | str) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path | str) -> "Ledger":
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
