"""Pydantic schema contracts — the provider-neutral source of truth for structured output.

These flow through the phases: ``hypothesize`` emits ``Hypotheses`` (candidates, all ``open``,
each with a ``disconfirming_test``); the test loop gathers evidence; ``adjudicate`` emits an
``InvestigationResult`` (each hypothesis ``confirmed``/``ruled_out`` with supporting AND
contradicting evidence).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    """A single grounded claim. ``source`` is what the citation verifier re-opens (Inc 2)."""

    claim: str = Field(
        description="The factual claim this evidence supports or refutes."
    )
    snippet: str = Field(
        description="A short verbatim quote copied from the source line."
    )
    source: str = Field(
        description="Citation as '<path>:<line>', e.g. 'telemetry/logs/redis.log:59'. "
        "Must be a path returned by the tools."
    )


class Hypothesis(BaseModel):
    """A candidate cause that evolves: open -> confirmed | ruled_out as evidence arrives."""

    id: str = Field(default="", description="Short id, e.g. 'H1'.")
    statement: str = Field(description="The proposed cause in one sentence.")
    service: str | None = Field(
        default=None,
        description="The service most likely AT FAULT (the root cause) — the service whose change "
        "or failure triggered the incident, NOT the affected/symptomatic service.",
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Calibrated confidence, 0..1."
    )
    status: Literal["open", "confirmed", "ruled_out"] = Field(
        default="open",
        description="'open' until tested; 'confirmed' if evidence supports it; 'ruled_out' if "
        "disconfirming evidence refutes it.",
    )
    disconfirming_test: str = Field(
        default="",
        description="The specific evidence that would prove THIS hypothesis wrong (what to go check).",
    )
    supporting: list[EvidenceRef] = Field(
        default_factory=list,
        description="Evidence that supports this hypothesis, each cited.",
    )
    contradicting: list[EvidenceRef] = Field(
        default_factory=list,
        description="Evidence that refutes this hypothesis, each cited.",
    )
    ruled_out_reason: str | None = Field(
        default=None,
        description="If ruled_out, the one-line reason (e.g. timing gap, rollback didn't fix it).",
    )


class Hypotheses(BaseModel):
    """Output of the hypothesize phase: the initial candidate set."""

    hypotheses: list[Hypothesis] = Field(
        description="Candidate causes — INCLUDING the most obvious one. Each 'open', each with a "
        "disconfirming_test; no evidence gathered yet."
    )


class InvestigationResult(BaseModel):
    """The adjudicated verdict."""

    query: str = Field(description="The incident report being investigated.")
    summary: str = Field(
        description="A 2-3 sentence plain-English briefing of what is happening."
    )
    hypotheses: list[Hypothesis] = Field(
        description="All hypotheses with final status, confidence, and supporting/contradicting "
        "evidence; ranked most-likely first."
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="Honest gaps — evidence that was missing or could not be checked.",
    )
    recommended_action: str | None = Field(
        default=None, description="The single most useful next action."
    )
