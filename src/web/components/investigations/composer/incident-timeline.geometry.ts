/**
 * Pure layout math for the incident-timeline strip — maps the corpus span + the previewed window to
 * SVG coordinates. Kept separate from the component (à la `blast-radius.graph.ts`) so it's trivially
 * unit-testable and the component stays declarative. No DOM, no React, no time-of-day reads.
 */
export const VIEW_W = 600;
export const TRACK_H = 36;
export const TRACK_Y = 14; // top padding leaves room for the as-of clamp cap

const MIN_BAND_PX = 4; // a sub-pixel window (2h on an 8-day corpus) stays visible
const TICK_MIN_FRAC = 0.22; // even a 1-count bucket gets a legible tick

export type Tick = { x: number; h: number };
export type TimelineGeometry = {
  band: { x: number; w: number } | null; // the visible window
  asOfX: number | null; // the clamp line
  hidden: { x: number; w: number } | null; // everything after as-of (not visible to the agent)
  ticks: Tick[]; // signal-density histogram
};

export function buildTimeline(opts: {
  corpusMin: string | null;
  corpusMax: string | null;
  density: number[];
  window: [Date, Date] | null;
  asOf: Date | null;
  width?: number;
  trackHeight?: number;
}): TimelineGeometry | null {
  const { corpusMin, corpusMax, density } = opts;
  const width = opts.width ?? VIEW_W;
  const trackHeight = opts.trackHeight ?? TRACK_H;
  if (!corpusMin || !corpusMax) return null;
  const t0 = new Date(corpusMin).getTime();
  const t1 = new Date(corpusMax).getTime();
  if (!(t1 > t0)) return null;

  const span = t1 - t0;
  const xOf = (d: Date) => Math.min(1, Math.max(0, (d.getTime() - t0) / span)) * width;

  const maxCount = density.reduce((m, c) => Math.max(m, c), 0) || 1;
  const n = density.length || 1;
  const ticks: Tick[] = [];
  density.forEach((c, i) => {
    if (c > 0) {
      ticks.push({
        x: ((i + 0.5) / n) * width,
        h: trackHeight * (TICK_MIN_FRAC + (1 - TICK_MIN_FRAC) * Math.sqrt(c / maxCount)),
      });
    }
  });

  let band: TimelineGeometry["band"] = null;
  if (opts.window) {
    const x = xOf(opts.window[0]);
    band = { x, w: Math.max(MIN_BAND_PX, xOf(opts.window[1]) - x) };
  }

  let asOfX: number | null = null;
  let hidden: TimelineGeometry["hidden"] = null;
  if (opts.asOf) {
    asOfX = xOf(opts.asOf);
    if (asOfX < width) hidden = { x: asOfX, w: width - asOfX };
  }

  return { band, asOfX, hidden, ticks };
}
