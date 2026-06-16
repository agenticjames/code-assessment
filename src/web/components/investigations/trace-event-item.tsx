import type { ReactNode } from "react";

import type { TraceEvent } from "@/lib/contracts";
import { cn } from "@/lib/utils";

function Line({
  children,
  dim,
  className,
}: {
  children: ReactNode;
  dim?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "font-mono text-xs leading-relaxed",
        dim ? "text-muted-foreground" : "text-foreground",
        className,
      )}
    >
      {children}
    </div>
  );
}

const argstr = (args: Record<string, unknown>) =>
  Object.entries(args)
    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
    .join(", ");

const firstLine = (s: string) => s.split("\n").find((l) => l.trim())?.slice(0, 120) ?? "";

/** One trace event rendered by type — the discriminated union mirror of engine/trace.py. */
export function TraceEventItem({ event }: { event: TraceEvent }) {
  switch (event.type) {
    case "scenario":
      return (
        <Line dim>
          investigating <span className="text-foreground">{event.data.query}</span> ·{" "}
          {event.data.files} files in window
        </Line>
      );
    case "phase":
      return <div className="pt-2 text-xs font-medium text-info">▸ {event.data.name}</div>;
    case "hypotheses":
      return (
        <div className="space-y-0.5">
          {event.data.hypotheses.map((h) => (
            <Line key={h.id}>
              <span className="text-muted-foreground">{h.id}</span> {h.statement}{" "}
              <span className="text-muted-foreground">(prior {Math.round(h.confidence * 100)}%)</span>
            </Line>
          ))}
        </div>
      );
    case "tool_call":
      return (
        <Line>
          <span className="text-muted-foreground">step {event.data.step}</span>{" "}
          <span className="text-info">{event.data.name}</span>(
          <span className="text-muted-foreground">{argstr(event.data.args)}</span>)
        </Line>
      );
    case "tool_result":
      return <Line dim>→ {firstLine(event.data.preview)}</Line>;
    case "thinking_done":
      return <Line dim>done gathering — emitting verdict</Line>;
    case "budget_exhausted":
      return <Line className="text-warning">step budget ({event.data.max_steps}) exhausted</Line>;
    case "error":
      return <Line className="text-destructive">error: {event.data.message}</Line>;
    default:
      return null;
  }
}
