import { ScrollArea } from "@/components/ui/scroll-area";
import type { TraceEvent } from "@/lib/contracts";

import { TraceEventItem } from "./trace-event-item";

export function TracePanel({ events, running }: { events: TraceEvent[]; running: boolean }) {
  return (
    <ScrollArea className="h-[28rem] rounded-lg border p-3">
      {events.length === 0 && !running && (
        <p className="text-sm text-muted-foreground">No trace recorded.</p>
      )}
      <div className="space-y-0.5">
        {events.map((e) => (
          <TraceEventItem key={e.seq} event={e} />
        ))}
        {running && (
          <div className="flex items-center gap-2 pt-2 text-xs text-warning">
            <span className="size-1.5 animate-pulse rounded-full bg-warning" /> running…
          </div>
        )}
      </div>
    </ScrollArea>
  );
}
