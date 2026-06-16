"""The evidence vault — loads a workspace + scenario frame and serves time-scoped evidence.

Central Inc-0 responsibility: slice the shared ``telemetry/`` corpus to the incident window
``[as_of - look_back, as_of]`` and **clamp to as_of** (no hindsight). Standing-world docs
(topology, runbooks, ADRs) are timeless and returned whole.

Selection (Inc 0): live telemetry (windowed) + standing ops docs. Deliberately excluded —
``scenarios/**`` (frames + the HIDDEN_TRUTH answer key), chat/comms/tickets (Inc 1/3), and
``incident-library/**`` (Inc 5 memory). ``HIDDEN_TRUTH.md`` is *never* exposed to the agent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from biggy.engine.config import RunConfig
from biggy.engine.evidence.timeutil import extract_timestamp, parse_iso, parse_lookback

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
_WINDOWED = {"log", "csv", "jsonl", "deploys"}


@dataclass
class EvidenceFile:
    relpath: str
    kind: str  # log | csv | jsonl | deploys | doc
    category: str  # telemetry | standing
    lines: int
    time_range: tuple[datetime, datetime] | None = (
        None  # in-window span, telemetry only
    )


@dataclass
class Scenario:
    id: str
    query: str
    as_of: datetime
    look_back: str
    window: tuple[datetime, datetime]
    severity: str | None
    hidden_truth_path: Path | None  # for the grader ONLY — never surfaced to the agent


class Vault:
    def __init__(
        self,
        root: Path,
        workspace: dict,
        scenario: Scenario,
        manifest: list[EvidenceFile],
        ablate: set[str] | None = None,
    ):
        self.root = root
        self.workspace = workspace
        self.scenario = scenario
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
        scenario = cls._load_scenario(root, config)
        manifest = cls._build_manifest(root, scenario, ablate)
        return cls(root, workspace, scenario, manifest, ablate)

    @staticmethod
    def _load_scenario(root: Path, config: RunConfig) -> Scenario:
        if not config.scenario:
            raise ValueError(
                "a --scenario is required (it provides the incident time window)."
            )
        sdir = root / "scenarios"
        match = next(
            (
                d
                for d in sorted(sdir.iterdir())
                if d.is_dir()
                and (
                    d.name == config.scenario or d.name.split("-")[0] == config.scenario
                )
            ),
            None,
        )
        if match is None:
            raise FileNotFoundError(
                f"scenario {config.scenario!r} not found under {sdir}"
            )
        frame = yaml.safe_load((match / "query.yaml").read_text(encoding="utf-8"))
        as_of = parse_iso(str(frame["as_of"]))
        look_back = str(frame.get("look_back", "2h"))
        ht = match / "HIDDEN_TRUTH.md"
        return Scenario(
            id=str(frame.get("id", config.scenario)),
            query=config.query or frame.get("query", ""),
            as_of=as_of,
            look_back=look_back,
            window=(as_of - parse_lookback(look_back), as_of),
            severity=frame.get("severity"),
            hidden_truth_path=ht if ht.exists() else None,
        )

    @classmethod
    def _build_manifest(
        cls, root: Path, scenario: Scenario, ablate: set[str]
    ) -> list[EvidenceFile]:
        files: list[EvidenceFile] = []
        for subdir, pat, kind in _TELEMETRY_GLOBS:
            base = root / subdir
            for p in sorted(base.glob(pat)) if base.is_dir() else []:
                if not p.is_file():
                    continue
                if subdir.endswith("captures") and not cls._capture_in_window(
                    p.name, scenario
                ):
                    continue
                files.append(
                    cls._make_entry(
                        root,
                        p.relative_to(root).as_posix(),
                        kind,
                        "telemetry",
                        scenario,
                    )
                )
        for rel, kind in _TELEMETRY_SINGLES:
            if (root / rel).is_file():
                files.append(cls._make_entry(root, rel, kind, "telemetry", scenario))
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
                            scenario,
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
        cls, root: Path, rel: str, kind: str, category: str, scenario: Scenario
    ) -> EvidenceFile:
        lines = (root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        tr = None
        if kind in _WINDOWED:
            kept = [
                extract_timestamp(t)
                for _, t in cls._window_lines(kind, lines, scenario.window)
            ]
            kept = [t for t in kept if t]
            if kept:
                tr = (min(kept), max(kept))
        return EvidenceFile(
            relpath=rel, kind=kind, category=category, lines=len(lines), time_range=tr
        )

    @staticmethod
    def _capture_in_window(name: str, scenario: Scenario) -> bool:
        m = _CAPTURE_TS.search(name)
        if not m:
            return True
        d, hh, mm = m.groups()
        ts = parse_iso(f"{d}T{hh}:{mm}:00")
        return scenario.window[0] <= ts <= scenario.as_of

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
        return list(enumerate(lines, 1))  # doc: whole file

    def _wlabel(self) -> str:
        s, e = self.scenario.window
        return f"{s:%Y-%m-%dT%H:%M}–{e:%H:%M}Z"

    # ---------- tool surface ----------
    def _normalize(self, path: str) -> str | None:
        p = path.strip().lstrip("./").replace("\\", "/")
        if "HIDDEN_TRUTH" in p or ".." in p:
            return None
        if p in self._allowed:
            return p
        cands = [a for a in self._allowed if a.endswith("/" + p)]
        return cands[0] if len(cands) == 1 else None

    def list_evidence(self) -> str:
        out = [
            f"# Evidence manifest — telemetry sliced to {self._wlabel()}; standing docs are timeless"
        ]
        for cat in ("telemetry", "standing"):
            group = [e for e in self.manifest if e.category == cat]
            if not group:
                continue
            out.append(f"\n## {cat}")
            for e in group:
                span = (
                    f"  [{e.time_range[0]:%H:%M}–{e.time_range[1]:%H:%M}Z]"
                    if e.time_range
                    else ""
                )
                out.append(f"- {e.relpath} ({e.kind}, {e.lines} lines){span}")
        return "\n".join(out)

    def read_evidence(self, path: str) -> str:
        rel = self._normalize(path)
        if rel is None:
            return f"ERROR: {path!r} is not a readable evidence file. Call list_evidence() for valid paths."
        kind = next((e.kind for e in self.manifest if e.relpath == rel), "doc")
        lines = (
            (self.root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        )
        kept = self._window_lines(kind, lines, self.scenario.window)
        header = f"# {rel}"
        if kind in _WINDOWED:
            header += (
                f"  (window {self._wlabel()}; {len(kept)}/{len(lines)} lines in window)"
            )
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
            for ln, txt in self._window_lines(e.kind, lines, self.scenario.window):
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
        for ln, txt in self._window_lines("deploys", lines, self.scenario.window):
            s = txt.strip()
            if not s.startswith("- {"):  # skip the 'changes:' header, comments, blanks
                continue
            if service and f"service: {service}" not in txt:
                continue
            out.append(f"{rel}:{ln}: {s}")
        if not out:
            scope = f" for service {service!r}" if service else ""
            return f"No changes{scope} in the incident window ({self._wlabel()})."
        head = f"# changes in {self._wlabel()}" + (
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
        for ln, txt in self._window_lines("csv", lines, self.scenario.window):
            ts, _, val = txt.partition(",")
            try:
                rows.append((ln, ts.strip(), float(val)))
            except ValueError:
                continue  # header / malformed
        if not rows:
            return f"# {rel}\n(no data points in the incident window {self._wlabel()})"
        vals = [v for _, _, v in rows]
        peak_ln, peak_ts, peak_v = max(rows, key=lambda r: r[2])
        summary = (
            f"# {rel}  (window {self._wlabel()}; {len(rows)} points)\n"
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
