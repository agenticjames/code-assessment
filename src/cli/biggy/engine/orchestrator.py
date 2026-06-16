"""The orchestrator — plain-Python control flow with one bounded tool loop (ARCHITECTURE §3.1/§3.3).

Inc 0 is the thinnest real thread: load the vault, run the agent's tool loop over time-scoped
evidence, then emit a structured, cited verdict. Each step is a node-shaped function so Inc 1
(multi-hypothesis + disconfirmation) and a future LangGraph port are near-zero refactors.
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from biggy.engine.config import RunConfig
from biggy.engine.ledger import Ledger
from biggy.engine.llm import get_client
from biggy.engine.schemas import InvestigationResult
from biggy.engine.evidence.tools import make_tools
from biggy.engine.trace import Tracer
from biggy.engine.evidence.vault import Vault

_PROMPT_PATH = Path(__file__).parent / "prompts" / "system.md"


def investigate(
    config: RunConfig, tracer: Tracer | None = None
) -> tuple[InvestigationResult, Ledger]:
    """Run one investigation. Returns the verdict and the (serialisable) ledger."""
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

    tools = make_tools(vault)
    tool_map = {t.name: t for t in tools}
    llm = get_client(config.provider, config.model)
    model = llm.bind_tools(tools)

    messages = [
        SystemMessage(content=_PROMPT_PATH.read_text(encoding="utf-8")),
        HumanMessage(content=_opening(config, sc)),
    ]

    for step in range(1, config.max_steps + 1):
        ai = model.invoke(messages)
        messages.append(ai)
        calls = getattr(ai, "tool_calls", None) or []
        if not calls:
            tracer.thinking_done(step)
            break
        for call in calls:
            name = call["name"]
            args = call.get("args") or {}
            tracer.tool_call(step, name, args)
            tool = tool_map.get(name)
            if tool is None:
                out = (
                    f"ERROR: unknown tool {name!r}. Valid tools: {', '.join(tool_map)}."
                )
            else:
                try:
                    out = str(tool.invoke(args))
                except (
                    Exception
                ) as exc:  # feed tool errors back to the agent, don't crash
                    out = f"ERROR running {name}: {exc}"
            ledger.record_tool(step, name, args, out)
            messages.append(
                ToolMessage(content=out, tool_call_id=call.get("id") or name)
            )
    else:
        tracer.budget_exhausted(config.max_steps)

    emit = HumanMessage(
        content=(
            "Based ONLY on the evidence you gathered above, emit your structured verdict now. "
            "For each hypothesis set `service` to the culprit (the cause), not the victim that "
            "merely shows symptoms. Cite every claim as <path>:<line> exactly as it appeared in a "
            "tool result."
        )
    )
    result = llm.structured(InvestigationResult).invoke(messages + [emit])
    if isinstance(result, dict):
        result = InvestigationResult.model_validate(result)
    ledger.result = result
    return result, ledger


def _opening(config: RunConfig, scenario) -> str:
    s, e = scenario.window
    return (
        f"Incident report: {scenario.query!r}\n"
        f"Workspace: {config.workspace} | Scenario: {scenario.id} | "
        f"Severity: {scenario.severity or 'unknown'}\n"
        f"Investigate as of {scenario.as_of:%Y-%m-%dT%H:%M}Z, looking back {scenario.look_back} "
        f"(window {s:%H:%M}-{e:%H:%M}Z).\n"
        "Start by calling list_evidence()."
    )
