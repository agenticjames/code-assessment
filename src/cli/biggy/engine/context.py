"""The shared investigation context — the blackboard the phases read and mutate.

Built once at the start of a run; flows through the phase pipeline. The ``ledger`` is the evolving
state; ``transcript`` is the running LangChain message list the test loop builds and adjudicate reuses.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import BaseTool

from biggy.engine.config import RunConfig
from biggy.engine.evidence.tools import make_tools
from biggy.engine.evidence.vault import Vault
from biggy.engine.ledger import Ledger
from biggy.engine.llm import get_client
from biggy.engine.llm.client import LLMClient
from biggy.engine.trace import Tracer


class InvestigationCancelled(Exception):
    """Raised between steps when a cancel signal is observed; the worker marks the run canceled."""


@dataclass
class Investigation:
    """What every phase operates on. Phases read these and mutate ``ledger`` (+ ``transcript``)."""

    config: RunConfig
    vault: Vault
    llm: LLMClient
    tracer: Tracer
    ledger: Ledger
    tools: list[BaseTool]
    transcript: list[Any] = field(default_factory=list)
    # Injected by the worker (reads Redis ``cancel:{id}``); the CLI leaves it None (no-op).
    cancel_check: Callable[[], bool] | None = None

    @property
    def tool_map(self) -> dict[str, BaseTool]:
        return {t.name: t for t in self.tools}

    def should_cancel(self) -> bool:
        """True if a cancel signal is set. Checked between steps in the test loop."""
        return bool(self.cancel_check and self.cancel_check())

    @classmethod
    def start(
        cls,
        config: RunConfig,
        tracer: Tracer | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> "Investigation":
        tracer = tracer or Tracer()
        vault = Vault.load(config)
        sc = vault.scenario
        tracer.scenario(vault)
        ledger = Ledger(
            incident_id=f"{config.workspace}-{sc.id}",
            workspace=config.workspace,
            scenario=sc.id,
            query=sc.query,
            as_of=sc.as_of.isoformat(),
            window=[sc.window[0].isoformat(), sc.window[1].isoformat()],
        )
        return cls(
            config=config,
            vault=vault,
            llm=get_client(config.provider, config.model),
            tracer=tracer,
            ledger=ledger,
            tools=make_tools(vault),
            cancel_check=cancel_check,
        )
