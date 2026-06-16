"""Grade one investigation against a scenario's ``HIDDEN_TRUTH.md``.

The answer key (YAML front-matter) is read **after** the run — never fed to the agent. Grading
turns the assessment thesis into executable checks: cause, calibration, required citations,
explicit herring rejection, open questions, dropped noise, and memory recall. The scorecard is the
"I measure my agent" artifact; it should fail when the output is correct-looking but under-grounded.
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
_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "about",
    "after",
    "against",
    "also",
    "and",
    "are",
    "because",
    "before",
    "being",
    "between",
    "both",
    "but",
    "can",
    "could",
    "does",
    "from",
    "have",
    "into",
    "not",
    "only",
    "that",
    "the",
    "then",
    "this",
    "through",
    "with",
    "would",
}


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
    band = _BAND.search(spec.strip())
    if band:
        lo, hi = float(band.group(1)), float(band.group(2))
        a = 0.0 if actual is None else actual
        return lo <= a <= hi
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


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _norm(text: str) -> str:
    return " ".join(_TOKEN.findall(str(text).casefold()))


def _keywords(text: str) -> set[str]:
    return {
        tok
        for tok in _TOKEN.findall(str(text).casefold())
        if (len(tok) >= 4 or any(ch.isdigit() for ch in tok)) and tok not in _STOPWORDS
    }


def _matches_expectation(expected: str, texts: list[str]) -> bool:
    """Loose text match for prose expectations from the answer key.

    Hidden-truth bullets are human-readable, not canonical machine phrases. We therefore accept an
    exact normalized substring or a small keyword overlap. This catches missing concepts without
    requiring the agent to reproduce the answer key's wording.
    """
    expected_norm = _norm(expected)
    if not expected_norm:
        return True
    for text in texts:
        if expected_norm in _norm(text):
            return True

    keys = _keywords(expected)
    if not keys:
        return False
    threshold = 1 if len(keys) == 1 else 2
    for text in texts:
        haystack = set(_TOKEN.findall(str(text).casefold()))
        if len(keys & haystack) >= threshold:
            return True
    return False


def _missing_detail(expected: list[str], matched: list[bool]) -> str:
    missing = [e for e, ok in zip(expected, matched, strict=False) if not ok]
    if not missing:
        return ""
    preview = "; ".join(str(m)[:64] for m in missing[:2])
    return f"; missing: {preview}"


def _list_expectation_check(name: str, expected: list[str], texts: list[str]) -> Check:
    if not expected:
        return Check(name, "not specified", True)
    matched = [_matches_expectation(str(item), texts) for item in expected]
    n = sum(matched)
    return Check(
        name,
        f"{n}/{len(expected)} matched{_missing_detail([str(e) for e in expected], matched)}",
        n == len(expected),
    )


def _citation_path(source: str) -> str:
    return _TRAILING_LINE.sub("", source.strip().replace("\\", "/").lstrip("./"))


def _evidence_refs(ledger: Ledger):
    if not ledger.result:
        return []
    return [
        e
        for h in ledger.result.hypotheses
        for e in (h.supporting + h.contradicting)
    ]


def _citation_check(required: list[str], ledger: Ledger) -> Check:
    if not required:
        return Check("required citations", "not specified", True)
    refs = _evidence_refs(ledger)
    matched: list[bool] = []
    for spec in required:
        path, _, detail = str(spec).partition("::")
        path = path.strip().replace("\\", "/").lstrip("./")
        detail = detail.strip()
        refs_for_path = [r for r in refs if _citation_path(r.source) == path]
        if not refs_for_path:
            matched.append(False)
            continue
        if not detail:
            matched.append(True)
            continue
        texts = [f"{r.claim} {r.snippet} {r.source}" for r in refs_for_path]
        matched.append(_matches_expectation(detail, texts))
    n = sum(matched)
    return Check(
        "required citations",
        f"{n}/{len(required)} cited{_missing_detail([str(r) for r in required], matched)}",
        n == len(required),
    )


def _result_texts(ledger: Ledger) -> list[str]:
    result = ledger.result
    if result is None:
        return []
    texts: list[str] = [
        result.query,
        result.summary,
        result.recommended_action or "",
        getattr(result, "stakeholder_note", None) or "",
        *result.open_questions,
    ]
    for h in result.hypotheses:
        texts.extend(
            [
                h.id,
                h.statement,
                h.service or "",
                h.disconfirming_test,
                h.ruled_out_reason or "",
            ]
        )
        for e in h.supporting + h.contradicting:
            texts.extend([e.claim, e.snippet, e.source])
    for item in getattr(result, "noise_dropped", []) or []:
        texts.extend([getattr(item, "item", ""), getattr(item, "reason", "")])
    return texts


def _open_question_check(key: dict, ledger: Ledger) -> Check | None:
    expected = _as_list(key.get("expected_open_questions")) or _as_list(
        key.get("missing_evidence_named")
    )
    if not expected:
        return None
    texts = ledger.result.open_questions if ledger.result else []
    return _list_expectation_check("open questions", [str(e) for e in expected], texts)


def _noise_check(key: dict, ledger: Ledger) -> Check | None:
    expected = [str(e) for e in _as_list(key.get("noise_to_drop")) if str(e).strip()]
    if not expected:
        return None
    result = ledger.result
    noises = getattr(result, "noise_dropped", []) if result else []
    texts = [f"{getattr(n, 'item', '')} {getattr(n, 'reason', '')}" for n in noises]
    return _list_expectation_check("noise dropped", expected, texts)


def _memory_check(key: dict, ledger: Ledger) -> Check | None:
    expected = [str(e) for e in _as_list(key.get("memory_recall")) if str(e).strip()]
    if not expected:
        return None
    texts = _result_texts(ledger)
    matched = [any(exp.casefold() in text.casefold() for text in texts) for exp in expected]
    n = sum(matched)
    return Check(
        "memory recall",
        f"{n}/{len(expected)} recalled{_missing_detail(expected, matched)}",
        n == len(expected),
    )


def _expected_hypotheses_check(key: dict, ledger: Ledger) -> Check | None:
    expected = []
    for item in _as_list(key.get("expected_hypotheses")):
        if isinstance(item, dict):
            expected.append(str(item.get("label") or item.get("mechanism") or item))
        else:
            expected.append(str(item))
    if not expected:
        return None
    texts = []
    if ledger.result:
        texts = [f"{h.service or ''} {h.statement}" for h in ledger.result.hypotheses]
    return _list_expectation_check("expected hypotheses", expected, texts)


def _common_checks(key: dict, ledger: Ledger) -> list[Check]:
    checks = [_citation_check([str(c) for c in _as_list(key.get("required_citations"))], ledger)]
    for optional in (
        _open_question_check(key, ledger),
        _noise_check(key, ledger),
        _memory_check(key, ledger),
    ):
        if optional is not None:
            checks.append(optional)
    checks.append(_grounding_check(ledger))
    return checks


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
        explicit = bool(h and h.status == "ruled_out" and h.ruled_out_reason)
        detail = (
            f"{herring} ({h.status}, conf {h.confidence:.2f}, reason yes)"
            if explicit
            else f"{herring} ({h.status if h else 'absent'})"
        )
        checks.append(
            Check(
                "herring ruled out",
                detail,
                explicit,
            )
        )
    for svc, spec in (key.get("expected_confidence") or {}).items():
        h = by_service.get(svc.lower())
        actual = h.confidence if h else None
        av = "-" if actual is None else f"{actual:.2f}"
        checks.append(
            Check(f"conf {svc}", f"{av} vs {spec}", _check_range(actual, str(spec)))
        )
    checks.extend(_common_checks(key, ledger))
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
    ]
    expected_hypotheses = _expected_hypotheses_check(key, ledger)
    if expected_hypotheses is not None:
        checks.append(expected_hypotheses)
    open_questions = _open_question_check(key, ledger)
    if open_questions is not None:
        checks.append(open_questions)
    else:
        checks.append(
            Check(
                "names missing evidence",
                f"{len(result.open_questions) if result else 0} open question(s); key expects {n_missing}",
                bool(result) and len(result.open_questions) >= 1,
            )
        )
    checks.extend(
        c
        for c in _common_checks(key, ledger)
        if c.name not in {"open questions"}
    )
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
