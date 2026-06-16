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
    ):
        self.root = root
        self.workspace = workspace
        self.scenario = scenario
        self.manifest = manifest
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
        scenario = cls._load_scenario(root, config)
        manifest = cls._build_manifest(root, scenario)
        return cls(root, workspace, scenario, manifest)

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
    def _build_manifest(cls, root: Path, scenario: Scenario) -> list[EvidenceFile]:
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
        # Hard guard: the answer key is never evidence.
        return [f for f in files if "HIDDEN_TRUTH" not in f.relpath]

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
