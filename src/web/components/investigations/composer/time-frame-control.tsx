"use client";

import { Clock } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { CorpusProfile } from "@/lib/manifest";
import { cn } from "@/lib/utils";
import {
  DEFAULT_LOOK_BACK,
  LOOK_BACK_OPTIONS,
  isoToLocalInput,
  localInputToIso,
  nowIso,
  type FrameInput,
  type FrameMode,
} from "@/lib/timeframe";

import { IncidentTimeline } from "./incident-timeline";

const MODES: { value: FrameMode; label: string }[] = [
  { value: "live", label: "Live" },
  { value: "retrospective", label: "Range" },
];

/**
 * First-class incident time frame: a Live (as-of + look-back) / Range (since–until) toggle. All
 * datetimes are UTC wall-clock (the corpus is UTC-anchored). Pure controlled component — it owns no
 * state; the parent composer holds the `FrameInput` and mirrors it into hidden form fields.
 */
export function TimeFrameControl({
  frame,
  onChange,
  corpus,
}: {
  frame: FrameInput;
  onChange: (frame: FrameInput) => void;
  corpus?: CorpusProfile | null;
}) {
  const setMode = (mode: FrameMode) => {
    if (mode === frame.mode) return;
    onChange(mode === "live" ? { mode, lookBack: DEFAULT_LOOK_BACK } : { mode });
  };

  return (
    <div className="space-y-3 rounded-md border border-border/60 bg-muted/30 p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium">Time frame</span>
        <div className="inline-flex rounded-md border p-0.5">
          {MODES.map((m) => (
            <button
              key={m.value}
              type="button"
              onClick={() => setMode(m.value)}
              aria-pressed={frame.mode === m.value}
              className={cn(
                "rounded px-2.5 py-1 text-xs transition-colors",
                frame.mode === m.value
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {frame.mode === "live" ? (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>Investigate as of</span>
          <Input
            type="datetime-local"
            aria-label="Investigate as of (UTC)"
            className="h-7 w-auto text-xs"
            value={isoToLocalInput(frame.asOf)}
            onChange={(e) => onChange({ ...frame, asOf: localInputToIso(e.target.value) })}
          />
          <span className="text-[10px] tracking-wide uppercase">UTC</span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onChange({ ...frame, asOf: nowIso() })}
          >
            <Clock /> Now
          </Button>
          <span className="ml-1">looking back</span>
          <Select
            value={frame.lookBack || DEFAULT_LOOK_BACK}
            onValueChange={(value) => onChange({ ...frame, lookBack: String(value) })}
          >
            <SelectTrigger size="sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {LOOK_BACK_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>From</span>
          <Input
            type="datetime-local"
            aria-label="Range start (UTC)"
            className="h-7 w-auto text-xs"
            value={isoToLocalInput(frame.since)}
            onChange={(e) => onChange({ ...frame, since: localInputToIso(e.target.value) })}
          />
          <span>to</span>
          <Input
            type="datetime-local"
            aria-label="Range end (UTC)"
            className="h-7 w-auto text-xs"
            value={isoToLocalInput(frame.until)}
            onChange={(e) => onChange({ ...frame, until: localInputToIso(e.target.value) })}
          />
          <span className="text-[10px] tracking-wide uppercase">UTC</span>
        </div>
      )}

      {corpus ? <IncidentTimeline corpus={corpus} frame={frame} /> : null}
    </div>
  );
}
