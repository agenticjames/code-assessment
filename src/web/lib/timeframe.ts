/**
 * The incident time frame on the web — the **preview-only mirror** of the engine's `frame.py`.
 *
 * The composer collects a `FrameInput` (mode + as-of/look-back, or a since/until range) and the
 * server action forwards it raw to the worker, where `resolve_frame` produces the *authoritative*
 * window. The math here (`previewWindow`) only drives the at-rest timeline preview before submit;
 * it deliberately duplicates the trivial `as_of − look_back` arithmetic (as `contracts.ts` mirrors
 * the wire shape) and nothing else — all telemetry semantics stay in the engine.
 *
 * Everything here is pure + isomorphic (safe in both server and client components).
 */
import type { ScenarioSeed } from "@/lib/manifest";

export type FrameMode = "live" | "retrospective";

/** What the composer collects and the server action forwards (mirrors RunConfig's frame inputs). */
export type FrameInput = {
  mode: FrameMode;
  asOf?: string; // ISO-8601 UTC (live)
  lookBack?: string; // e.g. "2h" (live)
  since?: string; // ISO-8601 UTC (retrospective)
  until?: string; // ISO-8601 UTC (retrospective)
};

export const DEFAULT_LOOK_BACK = "2h";

/** The look-back durations offered in the composer. Values mirror engine `parse_lookback` units. */
export const LOOK_BACK_OPTIONS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "30m", label: "30 minutes" },
  { value: "1h", label: "1 hour" },
  { value: "2h", label: "2 hours" },
  { value: "6h", label: "6 hours" },
  { value: "24h", label: "24 hours" },
  { value: "3d", label: "3 days" },
  { value: "5d", label: "5 days" },
];

const UNIT_MS: Record<string, number> = { s: 1e3, m: 60e3, h: 3.6e6, d: 8.64e7 };

/** Mirror of engine `parse_lookback`: "2h" / "90m" / "5d" → milliseconds, or null if malformed. */
export function lookBackMs(s: string): number | null {
  const m = /^(\d+)\s*([smhd])$/.exec(s.trim().toLowerCase());
  return m ? Number(m[1]) * UNIT_MS[m[2]] : null;
}

/**
 * The previewed `[start, end]` window for a frame input, or null if it's incomplete/malformed.
 * Authoritative resolution still happens in the engine — this only feeds the timeline preview.
 */
export function previewWindow(input: FrameInput): [Date, Date] | null {
  if (input.mode === "retrospective") {
    if (!input.since || !input.until) return null;
    const since = new Date(input.since);
    const until = new Date(input.until);
    return isNaN(+since) || isNaN(+until) ? null : [since, until];
  }
  const asOf = input.asOf ? new Date(input.asOf) : new Date();
  if (isNaN(+asOf)) return null;
  const ms = lookBackMs(input.lookBack || DEFAULT_LOOK_BACK);
  return ms == null ? null : [new Date(asOf.getTime() - ms), asOf];
}

/** Seed a `FrameInput` from a manifest scenario preset (so picking a preset fills the control). */
export function frameFromSeed(seed: ScenarioSeed): FrameInput {
  if (seed.mode === "retrospective" && seed.range) {
    return { mode: "retrospective", since: seed.range.from, until: seed.range.to };
  }
  return {
    mode: "live",
    asOf: seed.as_of ?? undefined,
    lookBack: seed.look_back ?? DEFAULT_LOOK_BACK,
  };
}

/** True once a frame input is complete enough to resolve a window (drives the submit/preview gates). */
export function hasCompleteFrame(input: FrameInput): boolean {
  return previewWindow(input) != null;
}

/** Current instant as an ISO-8601 UTC string (the "Now" button). */
export function nowIso(): string {
  return new Date().toISOString();
}

const _pad2 = (n: number) => String(n).padStart(2, "0");

/**
 * ISO instant → the value for `<input type="datetime-local">`, expressed in **UTC wall-clock**.
 * The corpus is UTC-anchored, so the control always shows/edits UTC (labelled as such) — never the
 * browser's local zone. Pairs with `localInputToIso`.
 */
export function isoToLocalInput(iso: string | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(+d)) return "";
  return (
    `${d.getUTCFullYear()}-${_pad2(d.getUTCMonth() + 1)}-${_pad2(d.getUTCDate())}` +
    `T${_pad2(d.getUTCHours())}:${_pad2(d.getUTCMinutes())}`
  );
}

/** `<input type="datetime-local">` value (read as UTC wall-clock) → ISO-8601 UTC instant. */
export function localInputToIso(value: string): string | undefined {
  if (!value) return undefined;
  const withSecs = value.length === 16 ? `${value}:00` : value; // add seconds if absent
  return `${withSecs}Z`;
}
