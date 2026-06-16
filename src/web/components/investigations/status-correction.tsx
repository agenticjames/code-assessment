import type { StatusCheck } from "@/lib/contracts";

/** The deterministic "correct the public status draft" callout — the visible "resist the human
 * consensus" moment. Mirrors cli/render.py `_status_panel`. Renders only when a divergence is found. */
export function StatusCorrection({ check }: { check: StatusCheck | null | undefined }) {
  if (!check || !check.needs_correction) return null;
  return (
    <div className="rounded-lg border border-warning/40 bg-warning/5 p-3">
      <p className="text-[11px] font-medium tracking-wide text-warning uppercase">
        Status-page correction <span className="normal-case opacity-70">(public draft vs evidence)</span>
      </p>
      <p className="mt-1 text-sm">{check.message}</p>
      {check.draft_source && <p className="mt-1 text-xs text-muted-foreground">draft: {check.draft_source}</p>}
    </div>
  );
}
