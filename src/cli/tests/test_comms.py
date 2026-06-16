"""Comms exposure + windowing — the messy human signal (chat / tickets / status) is now served
to the agent, time-scoped exactly like telemetry. All offline (no LLM).

These lock the two correctness properties the exposure depends on: the comms timestamp formats
window correctly (date-header carry for chat/status; inline ISO with optional seconds for
tickets), and the cause-naming RESOLUTIONS that live in the same continuous files stay out of a
live scenario's window (no hindsight)."""

from __future__ import annotations

from biggy.engine.comms import assess_impact, check_status
from biggy.engine.config import RunConfig
from biggy.engine.evidence.vault import Vault
from biggy.engine.schemas import Hypothesis, InvestigationResult


def _confirmed(service: str) -> InvestigationResult:
    return InvestigationResult(
        query="q",
        summary="s",
        hypotheses=[
            Hypothesis(
                id="H1", statement="x", service=service, confidence=0.9, status="confirmed"
            )
        ],
    )


def test_comms_files_surface_as_a_distinct_low_trust_class(config_a):
    v = Vault.load(config_a)
    comms = {e.relpath for e in v.manifest if e.category == "comms"}
    assert comms == {
        "telemetry/chat/incidents.md",
        "telemetry/support-tickets.md",
        "telemetry/status-updates.md",
    }
    listing = v.list_evidence()
    assert "telemetry/chat/incidents.md" in listing  # in the catalogue the agent sees
    assert "UNVERIFIED" in listing  # framed as low-trust, not ground truth


def test_chat_is_date_carry_windowed(config_a):
    v = Vault.load(config_a)  # window 13:15–15:15 on 2026-06-16
    chat = v.read_evidence("telemetry/chat/incidents.md")
    assert "we ran the orders-db migration" in chat  # 06-16 war room is in-window
    assert "## 2026-06-16" in chat  # the day header is carried down for context
    # the 06-10 auth storm + 06-12 promo live in the SAME file but are sliced out
    assert "## 2026-06-10" not in chat
    assert "auth got a memory-limit cut" not in chat
    assert "Valentine" not in chat


def test_tickets_window_with_optional_seconds(config_a):
    v = Vault.load(config_a)
    tix = v.read_evidence("telemetry/support-tickets.md")
    # the 06-16 checkout tickets (inline ISO is HH:MM, no seconds) are in-window...
    assert "ZD-4471" in tix and "ZD-4476" in tix
    # ...and the earlier auth ticket is not (the file is NOT date-sorted; each line self-dates)
    assert "ZD-4310" not in tix
    assert "revenue note" in tix  # the '#'-comment context line is kept


def test_status_draft_in_window_but_resolutions_excluded(config_a):
    v = Vault.load(config_a)
    status = v.read_evidence("telemetry/status-updates.md")
    assert "DRAFT" in status and "database migration" in status  # the wrong draft to correct
    assert "rollback at 14:58 did not resolve" in status  # multi-line draft body comes through
    # the 06-10/06-12 RESOLVED postmortems (which name a cause) are after their own as_of → absent
    assert "authentication service was reverted" not in status


def test_search_now_reaches_comms(config_a):
    v = Vault.load(config_a)
    assert "telemetry/chat/incidents.md" in v.search("ignore the disk alert")  # chat-only phrase
    assert "telemetry/support-tickets.md" in v.search("ZD-4471")  # ticket-only id


# ---- the deterministic comms pass (engine/comms.py) — no LLM ----


def test_impact_summarises_in_window_tickets(config_a):
    im = assess_impact(Vault.load(config_a))
    assert im.ticket_count == 4  # ZD-4471/4472/4475/4476 (06-16 checkout)
    assert im.top_priority == "urgent"
    assert im.services == ["checkout"]
    assert im.first_seen == "2026-06-16T14:51Z"
    assert im.revenue_note and "4.2k" in im.revenue_note
    assert all(s.startswith("telemetry/support-tickets.md:") for s in im.sources)


def test_status_check_flags_the_wrong_draft(config_a):
    sc = check_status(Vault.load(config_a), _confirmed("rate-limiter"))
    assert sc.has_draft and sc.needs_correction
    assert "database migration" in (sc.draft_excerpt or "")  # what the draft wrongly blames
    assert sc.verdict_cause == "rate-limiter"
    assert "rate-limiter" in (sc.message or "")
    assert (sc.draft_source or "").startswith("telemetry/status-updates.md:")


def test_status_check_does_not_flag_when_cause_is_in_the_draft(config_a):
    # discrimination check: if the confirmed cause is already named in the draft, no correction
    # fires (the draft mentions "checkout", so a checkout verdict would match it).
    sc = check_status(Vault.load(config_a), _confirmed("checkout"))
    assert sc.has_draft and not sc.needs_correction


def test_status_check_no_draft_no_correction(ws_root):
    cfg = RunConfig(
        query="", workspace="acme-checkout", scenario="B", workspaces_root=ws_root
    )
    sc = check_status(Vault.load(cfg), _confirmed("auth-service"))
    assert not sc.has_draft and not sc.needs_correction  # B's in-window status is 'investigating'


# ---- the leak fix: the war room must not RESOLVE inside a live scenario's window ----


def test_chat_does_not_leak_the_answer_for_a(config_a):
    chat = Vault.load(config_a).read_evidence("telemetry/chat/incidents.md")
    # the messy human signal IS in-window: the wrong consensus + priya's dismissed timing clue
    assert "we ran the orders-db migration" in chat  # dana's wrong consensus (the trap)
    assert "lines up almost exactly with the rate-limiter" in chat  # principle #4: dismissed clue
    # but the RESOLUTION + mechanism confirmation are re-authored past as_of (15:15)
    assert "connected_clients is pegged at 50" not in chat
    assert "roll back dep-7e2a" not in chat
    assert "got talked over" not in chat


def test_chat_does_not_leak_the_answer_for_e(ws_root):
    cfg = RunConfig(
        query="", workspace="acme-checkout", scenario="E", workspaces_root=ws_root
    )
    chat = Vault.load(cfg).read_evidence("telemetry/chat/incidents.md")
    assert "dep-5b71 search v2.9 deployed" in chat  # the deploy notice (public) is in-window
    assert "NPE in parseQuery" not in chat  # theo's diagnosis now lands past E's as_of (08:39)
    assert "rolling back" not in chat
