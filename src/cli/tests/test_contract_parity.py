"""Cross-language contract parity (docs/PHASE2.md §3 #4, §4.2).

The engine owns the trace-event vocabulary in ``biggy/engine/trace.py`` (``EVENT_*``); the worker
adds lifecycle events (``biggy/worker/contracts.py``). The web mirrors the whole union in
``src/web/lib/contracts.ts``. This test fails if the TS union drifts from the Python source — so
adding an event forces updating both sides.
"""

from __future__ import annotations

from pathlib import Path

import biggy.engine.trace as trace
from biggy.worker import contracts as wc

# src/cli/tests/test_contract_parity.py -> parents[3] is the repo root.
CONTRACTS_TS = (
    Path(__file__).resolve().parents[3] / "src" / "web" / "lib" / "contracts.ts"
)

ENGINE_EVENTS = {
    v for k, v in vars(trace).items() if k.startswith("EVENT_") and isinstance(v, str)
}
WORKER_EVENTS = {wc.EVENT_STATUS, wc.EVENT_ERROR, wc.EVENT_CANCELED, wc.EVENT_DONE}
ALL_EVENTS = ENGINE_EVENTS | WORKER_EVENTS


def test_contracts_ts_present() -> None:
    assert CONTRACTS_TS.is_file(), f"missing the TS contract mirror at {CONTRACTS_TS}"


def test_every_event_type_is_mirrored_in_typescript() -> None:
    text = CONTRACTS_TS.read_text(encoding="utf-8")
    for ev in sorted(ALL_EVENTS):
        assert f'"{ev}"' in text, (
            f'contracts.ts is missing trace event type "{ev}" — keep the union in sync with '
            "engine/trace.py + worker/contracts.py"
        )


def test_job_defaults_match_engine() -> None:
    # The Job model reuses the engine's RunConfig defaults — no second copy to drift.
    from biggy.engine.config import DEFAULT_MAX_STEPS, DEFAULT_MODEL, DEFAULT_PROVIDER

    job = wc.Job(id="x", query="q")
    assert job.provider == DEFAULT_PROVIDER
    assert job.model == DEFAULT_MODEL
    assert job.max_steps == DEFAULT_MAX_STEPS


def test_job_fields_mirrored_in_typescript() -> None:
    """Every Job field (incl. the frame inputs) must appear in jobSchema in contracts.ts."""
    text = CONTRACTS_TS.read_text(encoding="utf-8")
    start = text.index("export const jobSchema")
    block = text[start : text.index("});", start)]
    for field in wc.Job.model_fields:
        assert f"{field}:" in block, (
            f"contracts.ts jobSchema is missing Job field {field!r} — keep it in sync with "
            "worker/contracts.py Job"
        )
