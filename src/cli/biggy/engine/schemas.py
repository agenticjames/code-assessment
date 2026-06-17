"""Pydantic schema contracts — the provider-neutral source of truth for structured output.

These flow through the phases: ``hypothesize`` emits ``Hypotheses`` (candidates, all ``open``,
each with a ``disconfirming_test``); the test loop gathers evidence; ``adjudicate`` emits an
``InvestigationResult`` (each hypothesis ``confirmed``/``ruled_out`` with supporting AND
contradicting evidence).

Two tiers of schema live here, and the distinction matters when editing field text:

* **Model-facing** — ``Hypotheses``, ``Hypothesis``, ``EvidenceRef``, ``NoiseItem``,
  ``InvestigationResult``. The LLM fills these via ``with_structured_output``, so every class
  docstring and field ``description`` is *prompt surface*: it is fed to the model and shapes the
  graded output. Treat it like the phase prompts — preserve load-bearing wording and eval-gate any
  change (``biggy eval`` / the live ``test_orchestrator`` test); on the weak default model small
  rewordings perturb behaviour.
* **Code-only** — ``Grounding``, ``CustomerImpact``, ``StatusCheck`` (and ``EvidenceRef.verified``).
  Computed by the deterministic ``verify`` / ``reconcile`` phases and never emitted by the LLM, so
  their descriptions are internal documentation only — safe to edit freely.
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
    verified: bool | None = Field(
        default=None,
        description="Set by the deterministic verify phase (NOT the LLM): True if the snippet was "
        "found in the cited source. Leave unset.",
    )


class NoiseItem(BaseModel):
    """A signal the investigator deliberately dismissed as noise.

    The design's "explicitly drop, don't silently ignore" rule (DESIGN §3.3 #5): a chronic/unrelated
    alert that looked relevant but wasn't. Surfacing what was ruled OUT as noise is itself a trust
    signal — the responder sees the agent considered and dismissed it, not that it missed it.
    """

    item: str = Field(
        description="The dismissed signal, e.g. 'disk-space SEV4 on log-aggregator'."
    )
    reason: str = Field(
        description="One line on why it is noise, e.g. 'chronic pre-incident alert, unrelated to "
        "the 504 onset'."
    )


class Grounding(BaseModel):
    """Result of the deterministic citation verifier (computed by code, not the LLM)."""

    claims_total: int = Field(
        default=0, description="Total EvidenceRef citations across the verdict's hypotheses."
    )
    claims_verified: int = Field(
        default=0,
        description="How many of those citations the verifier re-grounded in their cited source.",
    )
    ungrounded: list[str] = Field(
        default_factory=list,
        description="Descriptions of citations whose snippet was not found in the cited source.",
    )


class CustomerImpact(BaseModel):
    """Customer-facing impact, derived deterministically (NOT by the LLM) from in-window support
    tickets — a grounded blast-radius/severity line for the briefing instead of a guess."""

    ticket_count: int = Field(
        default=0, description="Number of distinct in-window support tickets counted."
    )
    first_seen: str | None = Field(
        default=None, description="Earliest in-window ticket timestamp."
    )
    services: list[str] = Field(
        default_factory=list, description="Distinct affected service areas."
    )
    top_priority: str | None = Field(
        default=None, description="Highest ticket priority seen (urgent>high>normal>low)."
    )
    revenue_note: str | None = Field(
        default=None, description="A quantified revenue-impact note, if the tickets carry one."
    )
    sources: list[str] = Field(
        default_factory=list, description="'<path>:<line>' for each counted ticket."
    )


class StatusCheck(BaseModel):
    """Public status page cross-checked against the verdict — the deterministic 'correct the draft'
    callout. Catches a human consensus (a status DRAFT) that the evidence contradicts."""

    has_draft: bool = Field(
        default=False, description="True if an in-window public status draft was found."
    )
    draft_source: str | None = Field(
        default=None, description="'<path>:<line>' of the in-window draft."
    )
    draft_excerpt: str | None = Field(
        default=None, description="Short excerpt of the draft being cross-checked."
    )
    verdict_cause: str | None = Field(
        default=None, description="The confirmed cause the draft is checked against."
    )
    needs_correction: bool = Field(
        default=False,
        description="True if the draft's stated cause diverges from the verdict.",
    )
    message: str | None = Field(
        default=None,
        description="Responder-facing correction note when the draft diverges from the evidence.",
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
    outcome: Literal["root_cause", "inconclusive"] = Field(
        default="root_cause",
        description="'root_cause' if a cause is adequately supported by the evidence; "
        "'inconclusive' if the evidence cannot separate the candidates or the deciding evidence is "
        "missing — say so rather than fabricating a cause.",
    )
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
    stakeholder_note: str | None = Field(
        default=None,
        description="A short (2-4 sentence) plain-English update a responder could paste into the "
        "incident channel: what is happening, customer impact, the current best understanding of "
        "the cause WITH a confidence qualifier, and the next action. No jargon, no fabrication "
        "beyond the evidence; hedge if the outcome is inconclusive.",
    )
    noise_dropped: list[NoiseItem] = Field(
        default_factory=list,
        description="Signals that looked relevant but were deliberately dismissed as noise (e.g. a "
        "chronic/unrelated alert), each with a one-line reason. Shows what was ruled out, not missed.",
    )
