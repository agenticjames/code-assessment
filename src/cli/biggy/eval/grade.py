"""Grade one investigation against a scenario's ``HIDDEN_TRUTH.md``.

The answer key's YAML front-matter is read **after** the run (never fed to the agent). The Inc-2 bar
is the trust bar: the agent must name the cause, explicitly rule out the herring, return the right
`outcome`, **and** have every cited claim pass the deterministic verifier (grounding clean).
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


@dataclass
class Scorecard:
    scenario: str
    root_cause_service: str
    named_service: str | None
    named_is_top: bool
    named_correct: bool
    herring_service: str = ""
    herring_status: str | None = None
    herring_ruled_out: bool = False
    outcome_expected: str = ""
    outcome_actual: str = ""
    outcome_ok: bool = True
    grounding_total: int = 0
    grounding_verified: int = 0
    grounding_clean: bool = False
    confidence_checks: list[tuple[str, str, float | None, bool]] = field(
        default_factory=list
    )
    required_total: int = 0
    required_hit: int = 0
    required_detail: list[tuple[str, bool]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        # Inc 2 (trust) bar: right cause + herring ruled out + right outcome + all citations verified.
        herring_ok = not self.herring_service or self.herring_ruled_out
        return (
            self.named_correct
            and herring_ok
            and self.outcome_ok
            and self.grounding_clean
        )


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


def grade(ledger: Ledger, hidden_truth_path: Path | str) -> Scorecard:
    key = _front_matter(Path(hidden_truth_path))
    rc_service = str((key.get("root_cause") or {}).get("service", ""))
    herring_service = str((key.get("herring") or {}).get("service", ""))
    result = ledger.result

    hyps = sorted(result.hypotheses, key=lambda h: -h.confidence) if result else []
    by_service = {(h.service or "").lower(): h.confidence for h in reversed(hyps)}
    top = hyps[0] if hyps else None
    named = next(
        (h for h in hyps if (h.service or "").lower() == rc_service.lower()), None
    )
    herring = (
        next(
            (h for h in hyps if (h.service or "").lower() == herring_service.lower()),
            None,
        )
        if herring_service
        else None
    )

    outcome_expected = str(key.get("outcome", ""))
    outcome_actual = result.outcome if result else ""
    g = ledger.grounding

    card = Scorecard(
        scenario=str(key.get("scenario", "?")),
        root_cause_service=rc_service,
        named_service=top.service if top else None,
        named_is_top=bool(top and (top.service or "").lower() == rc_service.lower()),
        named_correct=named is not None,
        herring_service=herring_service,
        herring_status=herring.status if herring else None,
        herring_ruled_out=bool(herring and herring.status == "ruled_out"),
        outcome_expected=outcome_expected,
        outcome_actual=outcome_actual,
        outcome_ok=(not outcome_expected) or (outcome_actual == outcome_expected),
        grounding_total=g.claims_total if g else 0,
        grounding_verified=g.claims_verified if g else 0,
        grounding_clean=bool(
            g and g.claims_total > 0 and g.claims_verified == g.claims_total
        ),
    )
    for svc, spec in (key.get("expected_confidence") or {}).items():
        actual = by_service.get(svc.lower())
        card.confidence_checks.append(
            (svc, str(spec), actual, _check_range(actual, str(spec)))
        )

    cited_paths = {_TRAILING_LINE.sub("", s) for s in ledger.citations()}
    reqs = key.get("required_citations") or []
    for req in reqs:
        path = str(req).split("::")[0].strip()
        card.required_detail.append((path, path in cited_paths))
    card.required_total = len(reqs)
    card.required_hit = sum(1 for _, hit in card.required_detail if hit)
    return card


def scorecard_panel(card: Scorecard) -> Panel:
    def mark(ok: bool) -> str:
        return "[green]PASS[/]" if ok else "[red]FAIL[/]"

    t = Table(show_header=False, box=None, pad_edge=False)
    t.add_column(style="cyan", no_wrap=True)
    t.add_column()
    t.add_row("scenario", card.scenario)
    t.add_row("expected cause", escape(card.root_cause_service))
    named = f"{escape(card.named_service or '-')}  {mark(card.named_correct)}"
    t.add_row("named cause", named + ("  [dim](top)[/]" if card.named_is_top else ""))
    if card.herring_service:
        hs = card.herring_status or "absent"
        t.add_row(
            "herring ruled out",
            f"{escape(card.herring_service)} ({escape(hs)})  {mark(card.herring_ruled_out)}",
        )
    if card.outcome_expected:
        t.add_row(
            "outcome",
            f"{escape(card.outcome_actual or '-')} vs {escape(card.outcome_expected)}  "
            f"{mark(card.outcome_ok)}",
        )
    t.add_row(
        "grounding",
        f"{card.grounding_verified}/{card.grounding_total} verified  {mark(card.grounding_clean)}",
    )
    for svc, spec, actual, ok in card.confidence_checks:
        av = "-" if actual is None else f"{actual:.2f}"
        t.add_row(f"conf {escape(svc)}", f"{av} vs {escape(spec)}  {mark(ok)}")
    t.add_row(
        "citations", f"{card.required_hit}/{card.required_total} required paths cited"
    )
    for path, hit in card.required_detail:
        t.add_row("", f"{mark(hit)} [dim]{escape(path)}[/]")
    return Panel(
        t,
        title="[bold]Scorecard vs HIDDEN_TRUTH[/]",
        subtitle="[dim]Inc 2 bar: cause + herring ruled out + outcome + all citations verified[/]",
        border_style="green" if card.passed else "yellow",
        expand=False,
    )
