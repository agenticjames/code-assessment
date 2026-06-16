"""Pydantic schema contracts — the provider-neutral source of truth for structured output.

Inc 0 keeps these minimal (one cited hypothesis is enough to prove the thread). Inc 1/2
extend them (supporting/contradicting evidence, ruled-out hypotheses, grounding block).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    """A single grounded claim. ``source`` is what the citation verifier re-opens (Inc 2)."""

    claim: str = Field(description="The factual claim this evidence supports.")
    snippet: str = Field(
        description="A short verbatim quote copied from the source line."
    )
    source: str = Field(
        description="Citation as '<path>:<line>', e.g. 'telemetry/logs/redis.log:59'. "
        "Must be a path returned by the tools."
    )


class Hypothesis(BaseModel):
    """A candidate cause with calibrated confidence and its supporting evidence."""

    statement: str = Field(description="The proposed cause in one sentence.")
    service: str | None = Field(
        default=None,
        description="The service most likely AT FAULT (the root cause) — the service whose change "
        "or failure triggered the incident, NOT the affected/symptomatic service.",
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Calibrated confidence, 0..1."
    )
    evidence: list[EvidenceRef] = Field(
        default_factory=list,
        description="Evidence supporting this hypothesis, each cited.",
    )


class InvestigationResult(BaseModel):
    """The engine's structured verdict for one investigation."""

    query: str = Field(description="The incident report being investigated.")
    summary: str = Field(
        description="A 2-3 sentence plain-English briefing of what is happening."
    )
    hypotheses: list[Hypothesis] = Field(
        description="Candidate causes, ranked most-likely first."
    )
    recommended_action: str | None = Field(
        default=None, description="The single most useful next action."
    )
