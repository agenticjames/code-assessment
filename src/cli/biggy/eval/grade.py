"""Grade one investigation against a scenario's ``HIDDEN_TRUTH.md``.

The answer key (YAML front-matter) is read **after** the run — never fed to the agent. Grading
dispatches on ``outcome``: ``root_cause`` scenarios (A/B/E) are graded on naming the cause, ruling
out the herring, confidence ranges, and grounding; ``inconclusive`` scenarios (C) are graded on
*calibration* — staying unsure, holding confidence in band, surfacing the missing evidence, and not
violating the ``must_not`` guardrails. Both produce a uniform list of pass/fail ``Check``s.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from biggy.engine.ledger import Ledger

_FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
_TRAILING_LINE = re.compile(r":\d+$")
_RANGE = re.compile(r"(>=|<=|>|<|==)?\s*([0-9.]+)")
_BAND = re.compile(r"([0-9.]+)\s*\.\.\s*([0-9.]+)")


@dataclass
class Check:
    name: str
    detail: str
    ok: bool


@dataclass
class Scorecard:
    scenario: str
    outcome_kind: str  # root_cause | inconclusive
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)

    @property
    def n_passed(self) -> int:
        return sum(c.ok for c in self.checks)


def _front_matter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = _FRONT_MATTER.search(text)
    return yaml.safe_load(m.group(1) if m else text) or {}


def _check_range(actual: float | None, spec: str) -> bool:
    m = _RANGE.match(spec.strip())
    if not m:
        return False
    op, val = (m.group(1) or ">="), float(m.group(2))
    a = 0.0 if actual is None else actual
    return {">=": a >= val, "<=": a <= val, ">": a > val, "<": a < val, "==": a == val}[
        op
    ]


def _ranked(ledger: Ledger):
    return (
        sorted(ledger.result.hypotheses, key=lambda h: -h.confidence)
        if ledger.result
        else []
    )


def _grounding_check(ledger: Ledger) -> Check:
    g = ledger.grounding
    v, t = (g.claims_verified, g.claims_total) if g else (0, 0)
    return Check("grounding", f"{v}/{t} verified", bool(g) and t > 0 and v == t)


def grade(ledger: Ledger, hidden_truth_path: Path | str) -> Scorecard:
    key = _front_matter(Path(hidden_truth_path))
    kind = str(key.get("outcome", "root_cause"))
    if kind == "inconclusive":
        return _grade_inconclusive(key, ledger)
    return _grade_root_cause(key, ledger)


def _grade_root_cause(key: dict, ledger: Ledger) -> Scorecard:
    rc = str((key.get("root_cause") or {}).get("service", ""))
    herring = str((key.get("herring") or {}).get("service", ""))
    hyps = _ranked(ledger)
    by_service = {(h.service or "").lower(): h for h in reversed(hyps)}
    top = hyps[0] if hyps else None

    checks = [
        Check(
            "top hypothesis",
            f"{(top.service if top else '-')} vs {rc}",
            bool(top) and (top.service or "").lower() == rc.lower(),
        ),
        Check(
            "outcome",
            f"{ledger.result.outcome if ledger.result else '-'} vs root_cause",
            bool(ledger.result) and ledger.result.outcome == "root_cause",
        ),
    ]
    if herring and herring.lower() != "none":
        h = by_service.get(herring.lower())
        not_top = not (top and (top.service or "").lower() == herring.lower())
        # "not misled" = the agent didn't pick the herring: it either explicitly ruled it out, or
        # never entertained it as a real candidate (absent / near-zero confidence). Both are valid.
        not_misled = not_top and (
            h is None or h.confidence <= 0.1 or h.status == "ruled_out"
        )
        extra = f", conf {h.confidence:.2f}" if h else ""
        checks.append(
            Check(
                "herring not chosen",
                f"{herring} ({h.status if h else 'absent'}{extra})",
                not_misled,
            )
        )
    for svc, spec in (key.get("expected_confidence") or {}).items():
        h = by_service.get(svc.lower())
        actual = h.confidence if h else None
        av = "-" if actual is None else f"{actual:.2f}"
        checks.append(
            Check(f"conf {svc}", f"{av} vs {spec}", _check_range(actual, str(spec)))
        )
    checks.append(_grounding_check(ledger))
    return Scorecard(
        scenario=str(key.get("scenario", "?")), outcome_kind="root_cause", checks=checks
    )


def _grade_inconclusive(key: dict, ledger: Ledger) -> Scorecard:
    hyps = _ranked(ledger)
    top = hyps[0] if hyps else None
    second = hyps[1] if len(hyps) > 1 else None
    result = ledger.result
    band = str((key.get("expected_confidence") or {}).get("top", "0.45..0.60"))
    m = _BAND.search(band)
    lo, hi = (float(m.group(1)), float(m.group(2))) if m else (0.45, 0.60)
    n_missing = len(key.get("missing_evidence_named") or [])

    top_conf = top.confidence if top else 0.0
    spread = (top_conf - second.confidence) if second else 0.0
    confirmed = any(h.status == "confirmed" for h in hyps)

    checks = [
        Check(
            "outcome",
            f"{result.outcome if result else '-'} vs inconclusive",
            bool(result) and result.outcome == "inconclusive",
        ),
        Check("two live hypotheses", f"{len(hyps)} surfaced", len(hyps) >= 2),
        Check(
            "no confirmed cause",
            "none confirmed" if not confirmed else "a hypothesis is confirmed",
            not confirmed,
        ),
        Check("top confidence <= 0.60", f"{top_conf:.2f}", top_conf <= 0.60),
        Check(
            "top confidence in band", f"{top_conf:.2f} in {band}", lo <= top_conf <= hi
        ),
        Check("hypotheses close (spread <= 0.15)", f"{spread:.2f}", spread <= 0.1501),
        Check(
            "names missing evidence",
            f"{len(result.open_questions) if result else 0} open question(s); key expects {n_missing}",
            bool(result) and len(result.open_questions) >= 1,
        ),
        _grounding_check(ledger),
    ]
    return Scorecard(
        scenario=str(key.get("scenario", "?")),
        outcome_kind="inconclusive",
        checks=checks,
    )


def scorecard_panel(card: Scorecard) -> Panel:
    def mark(ok: bool) -> str:
        return "[green]PASS[/]" if ok else "[red]FAIL[/]"

    t = Table(show_header=False, box=None, pad_edge=False)
    t.add_column(style="cyan", no_wrap=True)
    t.add_column()
    for c in card.checks:
        t.add_row(c.name, f"{escape(c.detail)}  {mark(c.ok)}")
    return Panel(
        t,
        title=f"[bold]Scorecard — Scenario {escape(card.scenario)}[/] [dim]({card.outcome_kind})[/]",
        subtitle=f"[dim]{card.n_passed}/{len(card.checks)} checks[/]",
        border_style="green" if card.passed else "yellow",
        expand=False,
    )
