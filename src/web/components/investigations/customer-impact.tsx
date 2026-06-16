import type { CustomerImpact } from "@/lib/contracts";

/** Deterministic customer-impact line from in-window support tickets. Mirrors cli/render.py
 * `_impact_panel`. Renders nothing when there are no tickets. */
export function CustomerImpactCard({ impact }: { impact: CustomerImpact | null | undefined }) {
  if (!impact || impact.ticket_count === 0) return null;
  return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-3">
      <p className="text-[11px] font-medium tracking-wide text-destructive uppercase">
        Customer impact <span className="normal-case opacity-70">(deterministic, from support tickets)</span>
      </p>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-sm">
        <span>
          {impact.ticket_count} ticket{impact.ticket_count === 1 ? "" : "s"}
        </span>
        {impact.top_priority && (
          <span>
            · top priority <span className="font-medium">{impact.top_priority}</span>
          </span>
        )}
        {impact.services.length > 0 && <span>· {impact.services.join(", ")}</span>}
        {impact.first_seen && <span>· first {impact.first_seen}</span>}
      </div>
      {impact.revenue_note && <p className="mt-1 text-xs text-muted-foreground">{impact.revenue_note}</p>}
    </div>
  );
}
