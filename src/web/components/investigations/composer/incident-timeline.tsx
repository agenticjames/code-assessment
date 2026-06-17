"use client";

import { useMemo, useSyncExternalStore } from "react";

import { formatInstant, windowLabel } from "@/lib/format";
import type { CorpusProfile } from "@/lib/manifest";
import { previewWindow, type FrameInput } from "@/lib/timeframe";

import { buildTimeline, TRACK_H, TRACK_Y, VIEW_W } from "./incident-timeline.geometry";

const SVG_H = TRACK_Y + TRACK_H;
const subscribe = () => () => {};

/**
 * The incident-window strip: the previewed window highlighted on the telemetry corpus, with the
 * no-hindsight region (everything after as-of) shaded out and the signal-density histogram behind.
 * Reacts to the composer's frame so the user sees exactly what the agent will see. Preview only —
 * the engine resolves the authoritative window.
 */
export function IncidentTimeline({ corpus, frame }: { corpus: CorpusProfile; frame: FrameInput }) {
  // `previewWindow` may read the clock (live frame, no explicit as-of); compute it client-side only
  // so server and client first paints agree (no hydration mismatch). useSyncExternalStore gives the
  // client-only flag without a setState-in-effect.
  const isClient = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );

  const win = useMemo(() => (isClient ? previewWindow(frame) : null), [isClient, frame]);
  const geom = useMemo(
    () =>
      buildTimeline({
        corpusMin: corpus.min,
        corpusMax: corpus.max,
        density: corpus.density,
        window: win,
        asOf: win ? win[1] : null,
      }),
    [corpus, win],
  );

  if (corpus.min == null || corpus.max == null) return null;

  return (
    <div className="space-y-1.5">
      <svg
        viewBox={`0 0 ${VIEW_W} ${SVG_H}`}
        width="100%"
        height={SVG_H}
        preserveAspectRatio="none"
        role="img"
        aria-label="Incident window on the telemetry corpus"
        className="w-full"
      >
        <rect x={0} y={TRACK_Y} width={VIEW_W} height={TRACK_H} rx={4} className="fill-muted" />

        {geom?.ticks.map((t, i) => (
          <rect
            key={i}
            x={t.x - 0.75}
            y={TRACK_Y + TRACK_H - t.h}
            width={1.5}
            height={t.h}
            className="fill-muted-foreground/30"
          />
        ))}

        {geom?.hidden && (
          <rect
            x={geom.hidden.x}
            y={TRACK_Y}
            width={geom.hidden.w}
            height={TRACK_H}
            className="fill-foreground/5"
          />
        )}

        {geom?.band && (
          <rect
            x={geom.band.x}
            y={TRACK_Y}
            width={geom.band.w}
            height={TRACK_H}
            className="fill-primary/25 stroke-primary/50"
            strokeWidth={1}
          />
        )}

        {geom?.asOfX != null && (
          <line
            x1={geom.asOfX}
            y1={6}
            x2={geom.asOfX}
            y2={TRACK_Y + TRACK_H}
            className="stroke-primary"
            strokeWidth={1.5}
            strokeDasharray="3 2"
          />
        )}
      </svg>

      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
        <span>{formatInstant(corpus.min)}</span>
        <span className="font-medium text-foreground">
          {win ? windowLabel(win[0], win[1]) : "—"}
        </span>
        <span>{formatInstant(corpus.max)}</span>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted-foreground">
        <Swatch className="bg-primary/40" label="visible to agent" />
        <Swatch className="bg-foreground/10" label="not visible (clamped at as-of)" />
        <Swatch className="h-2 w-px bg-muted-foreground/40" label="signal density" />
      </div>
    </div>
  );
}

function Swatch({ className, label }: { className: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className={className.includes("w-px") ? className : `size-2 rounded-sm ${className}`} aria-hidden />
      {label}
    </span>
  );
}
