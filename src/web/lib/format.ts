/**
 * Shared formatters — one home for every display transform (docs/PHASE2.md §5). Pure + isomorphic
 * (safe in server and client components).
 */

export function confidencePct(c: number | null | undefined): string {
  if (c == null) return "—";
  return `${Math.round(c * 100)}%`;
}

export function duration(ms: number | null | undefined): string {
  if (ms == null) return "—";
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${s % 60}s`;
}

export function relativeTime(date: Date | string | null | undefined): string {
  if (!date) return "—";
  const d = typeof date === "string" ? new Date(date) : date;
  const secs = Math.round((Date.now() - d.getTime()) / 1000);
  if (secs < 5) return "just now";
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export function outcomeLabel(outcome: string | null | undefined): string {
  if (outcome === "inconclusive") return "Inconclusive";
  if (outcome === "root_cause") return "Root cause";
  return "—";
}

const STATUS_LABELS: Record<string, string> = {
  queued: "Queued",
  running: "Running",
  succeeded: "Done",
  failed: "Failed",
  canceled: "Canceled",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

export function isTerminal(status: string): boolean {
  return status === "succeeded" || status === "failed" || status === "canceled";
}

const _MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const _pad = (n: number) => String(n).padStart(2, "0");

/** ISO instant → compact, deterministic UTC display, e.g. "Jun 16, 15:15 UTC" (no locale → no
 * hydration drift). The corpus is UTC-anchored, so the UI always speaks UTC explicitly. */
export function formatInstant(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const d = typeof value === "string" ? new Date(value) : value;
  if (isNaN(+d)) return "—";
  return `${_MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${_pad(d.getUTCHours())}:${_pad(d.getUTCMinutes())} UTC`;
}

/** A window `[start, end]` → compact label; collapses to one date when both ends share a day. */
export function windowLabel(
  start: string | Date | null | undefined,
  end: string | Date | null | undefined,
): string {
  if (!start || !end) return "—";
  const s = typeof start === "string" ? new Date(start) : start;
  const e = typeof end === "string" ? new Date(end) : end;
  if (isNaN(+s) || isNaN(+e)) return "—";
  const t = (d: Date) => `${_pad(d.getUTCHours())}:${_pad(d.getUTCMinutes())}`;
  const sameDay =
    s.getUTCFullYear() === e.getUTCFullYear() &&
    s.getUTCMonth() === e.getUTCMonth() &&
    s.getUTCDate() === e.getUTCDate();
  if (sameDay) return `${_MONTHS[s.getUTCMonth()]} ${s.getUTCDate()}, ${t(s)}–${t(e)} UTC`;
  const dt = (d: Date) => `${_MONTHS[d.getUTCMonth()]} ${d.getUTCDate()} ${t(d)}`;
  return `${dt(s)} – ${dt(e)} UTC`;
}
