"""The Investigation Ledger — the engine's evolving, serialisable state.

Inc 0 records the tool calls (the visible reasoning trail) and the final verdict, and
serialises to ``ledger.json``. Inc 1 grows this into the multi-hypothesis / evidence /
timeline object from DESIGN §4.4.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from biggy.engine.schemas import InvestigationResult


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
    tool_calls: list[ToolCall] = Field(default_factory=list)
    result: InvestigationResult | None = None

    def record_tool(self, step: int, name: str, args: dict, result: str) -> None:
        preview = result if len(result) <= 280 else result[:277] + "..."
        self.tool_calls.append(
            ToolCall(step=step, name=name, args=args or {}, result_preview=preview)
        )

    def citations(self) -> list[str]:
        """Every citation source in the verdict's evidence (used by the grader)."""
        if not self.result:
            return []
        return [e.source for h in self.result.hypotheses for e in h.evidence]

    def to_json(self, path: Path | str) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path | str) -> "Ledger":
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
