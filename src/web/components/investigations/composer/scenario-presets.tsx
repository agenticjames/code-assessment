"use client";

import { Badge } from "@/components/ui/badge";
import type { ScenarioSeed } from "@/lib/manifest";

/**
 * The demo-incident quick-picks. Driven entirely by the workspace manifest (no hand-maintained
 * list) — selecting one fills the report + the time frame in the parent composer.
 */
export function ScenarioPresets({
  scenarios,
  selected,
  onSelect,
}: {
  scenarios: ScenarioSeed[];
  selected: string;
  onSelect: (seed: ScenarioSeed) => void;
}) {
  if (scenarios.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-xs text-muted-foreground">Load a demo incident:</span>
      {scenarios.map((s) => (
        <button
          key={s.id}
          type="button"
          onClick={() => onSelect(s)}
          className="cursor-pointer"
          aria-pressed={selected === s.id}
        >
          <Badge variant={selected === s.id ? "default" : "outline"}>
            {s.id} · {s.label}
          </Badge>
        </button>
      ))}
    </div>
  );
}
