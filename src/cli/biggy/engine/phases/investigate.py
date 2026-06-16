"""TEST — the bounded, disconfirmation-directed tool loop (the one piece of real agency).

Seeds the transcript with the hypotheses + their disconfirming_tests, then lets the model pull
evidence to REFUTE each (timing + shared dependencies) until it stops or the step budget runs out.
The transcript it builds is reused by adjudicate.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from biggy.engine.context import Investigation
from biggy.engine.phases.base import load_prompt


@dataclass
class Investigate:
    name: str = "investigate"

    def run(self, inv: Investigation) -> None:
        rendered = "\n".join(
            f"{h.id}: {h.statement} (service={h.service or '?'})\n"
            f"    disconfirming_test: {h.disconfirming_test}"
            for h in inv.ledger.initial_hypotheses
        )
        inv.transcript = [
            SystemMessage(content=load_prompt("investigate")),
            HumanMessage(
                content=f"Hypotheses to test:\n{rendered}\n\n"
                "Go get the evidence that would REFUTE each. Stop once one is confirmed and the "
                "others ruled out."
            ),
        ]
        model = inv.llm.bind_tools(inv.tools)
        tool_map = inv.tool_map

        for step in range(1, inv.config.max_steps + 1):
            ai = model.invoke(inv.transcript)
            inv.transcript.append(ai)
            calls = getattr(ai, "tool_calls", None) or []
            if not calls:
                inv.tracer.thinking_done(step)
                break
            for call in calls:
                name = call["name"]
                args = call.get("args") or {}
                inv.tracer.tool_call(step, name, args)
                tool = tool_map.get(name)
                if tool is None:
                    out = f"ERROR: unknown tool {name!r}. Valid tools: {', '.join(tool_map)}."
                else:
                    try:
                        out = str(tool.invoke(args))
                    except (
                        Exception
                    ) as exc:  # feed tool errors back to the agent, don't crash
                        out = f"ERROR running {name}: {exc}"
                inv.ledger.record_tool(step, name, args, out)
                inv.transcript.append(
                    ToolMessage(content=out, tool_call_id=call.get("id") or name)
                )
        else:
            inv.tracer.budget_exhausted(inv.config.max_steps)
