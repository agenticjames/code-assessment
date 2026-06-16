"""Wire contracts for the worker (docs/PHASE2.md §4.1/§4.2).

The Python mirror of ``src/web/lib/contracts.ts``. The trace-event vocabulary is owned by
``engine/trace.py`` (``EVENT_*``); the worker only adds the lifecycle events below. A parity test
(``tests/test_contract_parity.py``) keeps both languages in sync.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from biggy.engine.config import DEFAULT_MAX_STEPS, DEFAULT_MODEL, DEFAULT_PROVIDER

# Worker-added lifecycle events (the engine half lives in engine/trace.py EVENT_*).
EVENT_STATUS = "status"
EVENT_ERROR = "error"
EVENT_CANCELED = "canceled"
EVENT_DONE = "done"

# Terminal `done` payload states (also the investigations.status values).
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_CANCELED = "canceled"


class Job(BaseModel):
    """The unit of work Next enqueues and the worker claims. Mirrors ``jobSchema`` (zod)."""

    id: str
    query: str
    workspace: str = "acme-checkout"
    scenario: str | None = None
    provider: str = DEFAULT_PROVIDER
    model: str = DEFAULT_MODEL
    max_steps: int = Field(default=DEFAULT_MAX_STEPS, ge=1, le=30)
