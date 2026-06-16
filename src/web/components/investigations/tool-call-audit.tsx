import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { TraceEvent } from "@/lib/contracts";

/** The "what was called" audit, derived from the trace stream (tool_call + tool_result by step). */
export function ToolCallAudit({ events }: { events: TraceEvent[] }) {
  const calls = events.flatMap((e) => (e.type === "tool_call" ? [e] : []));
  const results = new Map<number, string>();
  for (const e of events) if (e.type === "tool_result") results.set(e.data.step, e.data.preview);

  if (!calls.length) {
    return <p className="text-sm text-muted-foreground">No tool calls recorded.</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-10">#</TableHead>
          <TableHead className="w-36">Tool</TableHead>
          <TableHead>Args</TableHead>
          <TableHead>Result</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {calls.map((e) => (
          <TableRow key={e.data.step}>
            <TableCell className="text-muted-foreground">{e.data.step}</TableCell>
            <TableCell className="font-mono text-info">{e.data.name}</TableCell>
            <TableCell className="font-mono text-xs text-muted-foreground">
              {JSON.stringify(e.data.args)}
            </TableCell>
            <TableCell className="max-w-0 truncate text-xs text-muted-foreground">
              {results.get(e.data.step)?.split("\n").find((l) => l.trim()) ?? ""}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
