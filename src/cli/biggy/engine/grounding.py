"""The deterministic citation verifier — the trust centerpiece.

Re-opens every cited source and confirms the quoted snippet actually appears there. **No LLM**: this
is the code the model cannot bluff past — the answer to "where is deterministic code better than the
agent?". It produces the grounding score and flags ungrounded claims, and is reusable in isolation
(the `verify` phase and a future API both call it).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from biggy.engine.schemas import Grounding, InvestigationResult

if TYPE_CHECKING:
    from biggy.engine.evidence.vault import Vault

_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    """Whitespace-collapsed + casefolded — lenient on formatting, strict on fabrication."""
    return _WS.sub(" ", text).strip().casefold()


def snippet_in_source(snippet: str, source_text: str | None) -> bool:
    """True iff the normalised snippet is a substring of the normalised cited source text."""
    if not source_text or not snippet or not snippet.strip():
        return False
    return _norm(snippet) in _norm(source_text)


def verify_citations(result: InvestigationResult, vault: "Vault") -> Grounding:
    """Check every cited claim against its source. Mutates each ``EvidenceRef.verified`` in place and
    returns the grounding score. ``vault.raw_text`` returns None for ablated/guarded/missing sources,
    which count as ungrounded."""
    total = verified = 0
    ungrounded: list[str] = []
    for h in result.hypotheses:
        for e in h.supporting + h.contradicting:
            total += 1
            ok = snippet_in_source(e.snippet, vault.raw_text(e.source))
            e.verified = ok
            if ok:
                verified += 1
            else:
                ungrounded.append(f"{e.source} — {e.claim}")
    return Grounding(
        claims_total=total, claims_verified=verified, ungrounded=ungrounded
    )
