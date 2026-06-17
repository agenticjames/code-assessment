"""The evidence vault — loads a workspace + a resolved TimeFrame and serves time-scoped evidence.

Central Inc-0 responsibility: slice the shared ``telemetry/`` corpus to the incident window
``[as_of - look_back, as_of]`` and **clamp to as_of** (no hindsight). Standing-world docs
(topology, runbooks, ADRs) are timeless and returned whole.

Selection: live telemetry (windowed) + **comms** — the messy human signal (chat, customer
tickets, status-page updates), windowed the same way but surfaced as a distinct, low-trust class
— + standing ops docs. Deliberately excluded: ``scenarios/**`` (frames + the HIDDEN_TRUTH answer
key) and ``incident-library/**`` (Inc 5 memory). ``HIDDEN_TRUTH.md`` is *never* exposed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from biggy.engine import scenario as scenario_mod
from biggy.engine.config import RunConfig
from biggy.engine.evidence.timeutil import extract_timestamp, parse_iso
from biggy.engine.frame import TimeFrame, resolve_frame

# (subdir, glob, kind) for telemetry served with windowing.
_TELEMETRY_GLOBS = [
    ("telemetry/logs", "*.log", "log"),
    ("telemetry/metrics", "*.csv", "csv"),
    ("telemetry/changes", "*.diff", "doc"),
    ("telemetry/captures", "*", "doc"),
]
_TELEMETRY_SINGLES = [
    ("telemetry/alerts.jsonl", "jsonl"),
    ("telemetry/deploys.yaml", "deploys"),
]
# The messy HUMAN signal — windowed like telemetry but a distinct, low-trust class (unverified;
# leads + customer impact, NOT ground truth). chat/status are date-header + time-only; tickets
# carry an inline ISO. Windowed by dedicated branches in ``_window_lines`` / ``_window_dated``.
_COMMS_GLOBS = [
    ("telemetry/chat", "*.md", "chat"),
]
_COMMS_SINGLES = [
    ("telemetry/support-tickets.md", "tickets"),
    ("telemetry/status-updates.md", "status"),
]
# (subdir | ".", glob, kind) for timeless standing-world docs.
_STANDING_GLOBS = [
    ("topology", "*.yaml", "doc"),
    ("runbooks", "*.md", "doc"),
    ("adr", "*.md", "doc"),
    ("monitors", "*.yaml", "doc"),
    (".", "slos.yaml", "doc"),
    (".", "teams.yaml", "doc"),
    (".", "GLOSSARY.md", "doc"),
]
_CAPTURE_TS = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2})(\d{2})Z")
# Comms timestamp shapes (see ``_window_dated`` and the tickets branch in ``_window_lines``).
_DATE_HDR = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})")
_CHAT_TS = re.compile(r"^\[(\d{2}):(\d{2})\]")
_STATUS_TS = re.compile(r"^- (\d{2}):(\d{2}) \[")
_TICKET_TS = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?Z")
_CAT_LABELS = {
    "telemetry": "telemetry",
    "comms": "comms  (human signal: chat / tickets / status — UNVERIFIED; leads + impact, "
    "corroborate against telemetry before trusting)",
    "standing": "standing",
}
_WINDOWED = {"log", "csv", "jsonl", "deploys", "chat", "status", "tickets"}


def _window_dated(
    kind: str, lines: list[str], start: datetime, end: datetime
) -> list[tuple[int, str]]:
    """Window a date-header + time-only file (chat / status). The ``## YYYY-MM-DD`` header carries
    down to each ``[HH:MM]`` (chat) / ``- HH:MM [`` (status) line; prose/blockquotes follow their
    parent; the section header is emitted once before its first in-window line so the day stays
    visible. ``parse_iso`` turns the combined ``date T time`` into the aware-UTC the window uses.
    """
    line_re = _CHAT_TS if kind == "chat" else _STATUS_TS
    cur_date: str | None = None
    pending_hdr: tuple[int, str] | None = None
    keep_prev = False
    out: list[tuple[int, str]] = []
    for i, txt in enumerate(lines, 1):
        d = _DATE_HDR.match(txt)
        if d:
            cur_date, pending_hdr, keep_prev = d.group(1), (i, txt), False
            continue
        m = line_re.match(txt)
        if m and cur_date:
            keep_prev = (
                start <= parse_iso(f"{cur_date}T{m.group(1)}:{m.group(2)}:00") <= end
            )
            if keep_prev:
                if pending_hdr:
                    out.append(pending_hdr)
                    pending_hdr = None
                out.append((i, txt))
        elif (
            txt.strip() and keep_prev
        ):  # prose / blockquote continuation follows its parent
            out.append((i, txt))
    return out


@dataclass
class EvidenceFile:
    relpath: str
    kind: str  # log | csv | jsonl | deploys | doc
    category: str  # telemetry | standing
    lines: int
    time_range: tuple[datetime, datetime] | None = (
        None  # in-window span, telemetry only
    )


class Vault:
    def __init__(
        self,
        root: Path,
        workspace: dict,
        frame: TimeFrame,
        query: str,
        scenario_id: str | None,
        severity: str | None,
        manifest: list[EvidenceFile],
        ablate: set[str] | None = None,
    ):
        self.root = root
        self.workspace = workspace
        self.frame = frame  # WHEN — the resolved time window + clamp
        self.query = query  # WHAT — the incident report
        self.scenario_id = scenario_id  # set for seeded/eval runs; None for ad-hoc
        self.severity = severity
        self.manifest = manifest
        self.ablate = ablate or set()
        self._allowed = {e.relpath for e in manifest}

    # ---------- loading ----------
    @classmethod
    def load(cls, config: RunConfig) -> "Vault":
        root = config.workspace_dir
        if not root.is_dir():
            raise FileNotFoundError(f"workspace not found: {root}")
        workspace = yaml.safe_load(
            (root / "workspace.yaml").read_text(encoding="utf-8")
        )
        ablate = {
            a.strip().replace("\\", "/").lstrip("./") for a in (config.ablate or [])
        }
        # A named scenario only *seeds* the query/severity now; the time window is resolved
        # independently (explicit flags > scenario seed > default now/2h), so an investigation can
        # run with no scenario at all. The answer key stays out of the vault entirely (grader-only).
        seed = (
            scenario_mod.read_seed(root, config.scenario) if config.scenario else None
        )
        frame = resolve_frame(config)
        query = config.query or (seed.query if seed else "")
        severity = seed.severity if seed else None
        manifest = cls._build_manifest(root, frame, ablate)
        return cls(
            root, workspace, frame, query, config.scenario, severity, manifest, ablate
        )

    @classmethod
    def _build_manifest(
        cls, root: Path, frame: TimeFrame, ablate: set[str]
    ) -> list[EvidenceFile]:
        files: list[EvidenceFile] = []
        for subdir, pat, kind in _TELEMETRY_GLOBS:
            base = root / subdir
            for p in sorted(base.glob(pat)) if base.is_dir() else []:
                if not p.is_file():
                    continue
                if subdir.endswith("captures") and not cls._capture_in_window(
                    p.name, frame
                ):
                    continue
                files.append(
                    cls._make_entry(
                        root,
                        p.relative_to(root).as_posix(),
                        kind,
                        "telemetry",
                        frame,
                    )
                )
        for rel, kind in _TELEMETRY_SINGLES:
            if (root / rel).is_file():
                files.append(cls._make_entry(root, rel, kind, "telemetry", frame))
        for subdir, pat, kind in _COMMS_GLOBS:
            base = root / subdir
            for p in sorted(base.glob(pat)) if base.is_dir() else []:
                if p.is_file():
                    files.append(
                        cls._make_entry(
                            root, p.relative_to(root).as_posix(), kind, "comms", frame
                        )
                    )
        for rel, kind in _COMMS_SINGLES:
            if (root / rel).is_file():
                files.append(cls._make_entry(root, rel, kind, "comms", frame))
        for subdir, pat, kind in _STANDING_GLOBS:
            base = root if subdir == "." else root / subdir
            for p in sorted(base.glob(pat)) if base.is_dir() else []:
                if p.is_file():
                    files.append(
                        cls._make_entry(
                            root,
                            p.relative_to(root).as_posix(),
                            kind,
                            "standing",
                            frame,
                        )
                    )
        # Hard guard: the answer key is never evidence; --ablate hides files (honesty demo).
        return [
            f
            for f in files
            if "HIDDEN_TRUTH" not in f.relpath and f.relpath not in ablate
        ]

    @classmethod
    def _make_entry(
        cls, root: Path, rel: str, kind: str, category: str, frame: TimeFrame
    ) -> EvidenceFile:
        lines = (root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        tr = None
        if kind in _WINDOWED:
            kept = [
                extract_timestamp(t)
                for _, t in cls._window_lines(kind, lines, frame.window)
            ]
            kept = [t for t in kept if t]
            if kept:
                tr = (min(kept), max(kept))
        return EvidenceFile(
            relpath=rel, kind=kind, category=category, lines=len(lines), time_range=tr
        )

    @staticmethod
    def _capture_in_window(name: str, frame: TimeFrame) -> bool:
        m = _CAPTURE_TS.search(name)
        if not m:
            return True
        d, hh, mm = m.groups()
        ts = parse_iso(f"{d}T{hh}:{mm}:00")
        return frame.window[0] <= ts <= frame.as_of

    # ---------- windowing ----------
    @staticmethod
    def _window_lines(
        kind: str, lines: list[str], window: tuple[datetime, datetime]
    ) -> list[tuple[int, str]]:
        start, end = window
        out: list[tuple[int, str]] = []
        if kind == "log":
            keep_prev = False
            for i, txt in enumerate(lines, 1):
                ts = extract_timestamp(txt)
                if ts is None:  # continuation (stack-trace frame) — follow its parent
                    if keep_prev:
                        out.append((i, txt))
                    continue
                keep_prev = start <= ts <= end
                if keep_prev:
                    out.append((i, txt))
            return out
        if kind == "csv":
            for i, txt in enumerate(lines, 1):
                ts = extract_timestamp(txt)
                if (
                    i == 1 or ts is None or start <= ts <= end
                ):  # keep header + in-window rows
                    out.append((i, txt))
            return out
        if kind in ("jsonl", "deploys"):
            for i, txt in enumerate(lines, 1):
                ts = extract_timestamp(txt)
                if (
                    ts is None or start <= ts <= end
                ):  # keep structural lines + in-window entries
                    out.append((i, txt))
            return out
        if kind in ("chat", "status"):  # date-header + time-only — carry the date down
            return _window_dated(kind, lines, start, end)
        if kind == "tickets":  # one inline ISO per line (seconds optional)
            for i, txt in enumerate(lines, 1):
                m = _TICKET_TS.search(txt)
                if (
                    m is None
                ):  # comment / blank / revenue-note: structural context, keep
                    if not txt.strip() or txt.lstrip().startswith("#"):
                        out.append((i, txt))
                    continue
                ts = parse_iso(
                    f"{m.group(1)}T{m.group(2)}:{m.group(3)}:{m.group(4) or '00'}"
                )
                if start <= ts <= end:
                    out.append((i, txt))
            return out
        return list(enumerate(lines, 1))  # doc: whole file

    # ---------- tool surface ----------
    def _normalize(self, path: str) -> str | None:
        p = path.strip().lstrip("./").replace("\\", "/")
        if "HIDDEN_TRUTH" in p or ".." in p:
            return None
        if p in self._allowed:
            return p
        cands = [a for a in self._allowed if a.endswith("/" + p)]
        return cands[0] if len(cands) == 1 else None

    def list_evidence(
        self, categories: tuple[str, ...] = ("telemetry", "comms", "standing")
    ) -> str:
        """The evidence catalogue. ``categories`` scopes what a phase sees: the hypothesize seed asks
        for telemetry+standing only — hypotheses come from what CHANGED and the machine signal, while
        comms are unverified human leads the TEST phase corroborates (seeding a hypothesis off hearsay
        is exactly what we avoid). The agent-facing tool uses the default (all categories)."""
        scoped = "telemetry + comms" if "comms" in categories else "telemetry"
        out = [
            f"# Evidence manifest — {scoped} sliced to {self.frame.label()}; standing docs are timeless"
        ]
        for cat in categories:
            group = [e for e in self.manifest if e.category == cat]
            if not group:
                continue
            out.append(f"\n## {_CAT_LABELS[cat]}")
            for e in group:
                span = (
                    f"  [{e.time_range[0]:%H:%M}–{e.time_range[1]:%H:%M}Z]"
                    if e.time_range
                    else ""
                )
                out.append(f"- {e.relpath} ({e.kind}, {e.lines} lines){span}")
        return "\n".join(out)

    def windowed(self, path: str) -> list[tuple[int, str]]:
        """In-window ``(line_no, text)`` pairs for a manifest file (``[]`` if not readable). The
        structured basis the deterministic comms pass reads (tickets / status), so it sees exactly
        the same time-scoped slice the agent does."""
        rel = self._normalize(path)
        if rel is None:
            return []
        kind = next((e.kind for e in self.manifest if e.relpath == rel), "doc")
        lines = (
            (self.root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        )
        return self._window_lines(kind, lines, self.frame.window)

    def read_evidence(self, path: str) -> str:
        rel = self._normalize(path)
        if rel is None:
            return f"ERROR: {path!r} is not a readable evidence file. Call list_evidence() for valid paths."
        kind = next((e.kind for e in self.manifest if e.relpath == rel), "doc")
        lines = (
            (self.root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        )
        kept = self._window_lines(kind, lines, self.frame.window)
        header = f"# {rel}"
        if kind in _WINDOWED:
            header += f"  (window {self.frame.label()}; {len(kept)}/{len(lines)} lines in window)"
        if not kept:
            return f"{header}\n(no entries in the incident window)"
        body = "\n".join(f"{ln}\t{txt}" for ln, txt in kept)
        return f"{header}\n{body}"

    def search(self, keyword: str, limit: int = 60) -> str:
        kw = keyword.strip().lower()
        if not kw:
            return "ERROR: empty keyword."
        hits: list[str] = []
        for e in self.manifest:
            lines = (
                (self.root / e.relpath)
                .read_text(encoding="utf-8", errors="replace")
                .splitlines()
            )
            for ln, txt in self._window_lines(e.kind, lines, self.frame.window):
                if kw in txt.lower():
                    hits.append(f"{e.relpath}:{ln}: {txt.strip()}")
                    if len(hits) >= limit:
                        break
            if len(hits) >= limit:
                break
        if not hits:
            return f"No matches for {keyword!r} in the incident window."
        return f"{len(hits)} match(es) for {keyword!r}:\n" + "\n".join(hits)

    # ---------- structured accessors (the get_* tools) ----------
    def get_topology(self, service: str) -> str:
        """A service's upstream deps + derived dependents + store specifics. Standing (no window)."""
        rel = "topology/services.yaml"
        topo = yaml.safe_load((self.root / rel).read_text(encoding="utf-8")) or {}
        svc = service.strip()
        if svc not in topo:
            ci = [k for k in topo if k.lower() == svc.lower()]
            if not ci:
                return f"ERROR: unknown service {service!r}. Known: {', '.join(sorted(topo))}."
            svc = ci[0]
        entry = topo[svc] or {}
        deps = entry.get("depends_on") or []
        dependents = sorted(
            k for k, v in topo.items() if svc in ((v or {}).get("depends_on") or [])
        )
        line = next(
            (
                i
                for i, t in enumerate(
                    (self.root / rel).read_text(encoding="utf-8").splitlines(), 1
                )
                if t.startswith(f"{svc}:")
            ),
            None,
        )
        src = f"{rel}:{line}" if line else rel
        out = [
            f"# {svc}  ({src})",
            f"tier: {entry.get('tier', '?')}  owner: {entry.get('owner', '?')}",
        ]
        if entry.get("slo"):
            out.append(f"slo: {entry['slo']}")
        out.append(f"depends_on (upstream): {deps or '[]'}")
        out.append(f"dependents (downstream, derived): {dependents or '[]'}")
        for k in ("type", "max_connections", "shared_by", "config", "external"):
            if k in entry:
                out.append(f"{k}: {entry[k]}")
        desc = (entry.get("description") or "").strip()
        if desc:
            out.append(f"description: {desc}")
        return "\n".join(out)

    def get_changes(self, service: str | None = None) -> str:
        """Deploys / config changes / migrations in the incident window, each source-anchored."""
        rel = "telemetry/deploys.yaml"
        lines = (
            (self.root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        )
        out = []
        for ln, txt in self._window_lines("deploys", lines, self.frame.window):
            s = txt.strip()
            if not s.startswith("- {"):  # skip the 'changes:' header, comments, blanks
                continue
            if service and f"service: {service}" not in txt:
                continue
            out.append(f"{rel}:{ln}: {s}")
        if not out:
            scope = f" for service {service!r}" if service else ""
            return f"No changes{scope} in the incident window ({self.frame.label()})."
        head = f"# changes in {self.frame.label()}" + (
            f" (service={service})" if service else ""
        )
        return head + "\n" + "\n".join(out)

    def get_metric(self, name: str) -> str:
        """A metric time-series in the incident window + a summary (peak / min / max), source-anchored."""
        stem = name.strip().removesuffix(".csv")
        rel = f"telemetry/metrics/{stem}.csv"
        full = self.root / rel
        if not full.is_file():
            avail = sorted(
                p.stem for p in (self.root / "telemetry/metrics").glob("*.csv")
            )
            return f"ERROR: unknown metric {name!r}. Available: {', '.join(avail)}."
        lines = full.read_text(encoding="utf-8", errors="replace").splitlines()
        rows = []
        for ln, txt in self._window_lines("csv", lines, self.frame.window):
            ts, _, val = txt.partition(",")
            try:
                rows.append((ln, ts.strip(), float(val)))
            except ValueError:
                continue  # header / malformed
        if not rows:
            return (
                f"# {rel}\n(no data points in the incident window {self.frame.label()})"
            )
        vals = [v for _, _, v in rows]
        peak_ln, peak_ts, peak_v = max(rows, key=lambda r: r[2])
        summary = (
            f"# {rel}  (window {self.frame.label()}; {len(rows)} points)\n"
            f"first={rows[0][2]:g} last={rows[-1][2]:g} min={min(vals):g} max={max(vals):g} "
            f"peak={peak_v:g} @ {peak_ts} ({rel}:{peak_ln})"
        )
        body = "\n".join(f"{rel}:{ln}: {ts},{v:g}" for ln, ts, v in rows)
        return f"{summary}\n{body}"

    # ---------- citation resolution (for the verifier, NOT the agent) ----------
    def raw_text(self, source: str) -> str | None:
        """Resolve a citation ('path' or 'path:line') to the real file's FULL text, or None if the
        path is ablated, guarded, or missing. The verifier checks the snippet against this."""
        m = re.match(r"^(.*?):\d+$", source.strip())
        path = (m.group(1) if m else source.strip()).replace("\\", "/").lstrip("./")
        if not path or "HIDDEN_TRUTH" in path or ".." in path or path in self.ablate:
            return None
        full = self.root / path
        if not full.is_file():
            return None
        return full.read_text(encoding="utf-8", errors="replace")
