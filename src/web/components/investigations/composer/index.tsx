"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useFormStatus } from "react-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { createInvestigation } from "@/lib/actions";
import type { Manifest, ScenarioSeed } from "@/lib/manifest";
import { DEFAULT_LOOK_BACK, frameFromSeed, type FrameInput } from "@/lib/timeframe";

import { ScenarioPresets } from "./scenario-presets";
import { TimeFrameControl } from "./time-frame-control";

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" disabled={pending}>
      {pending ? (
        <>
          <Loader2 className="animate-spin" /> Investigating…
        </>
      ) : (
        "Investigate"
      )}
    </Button>
  );
}

const INITIAL_FRAME: FrameInput = { mode: "live", lookBack: DEFAULT_LOOK_BACK };

/**
 * The "new investigation" composer. Owns the form state (report, time frame, scenario seed) and
 * mirrors the frame into hidden fields so the `createInvestigation` server action receives it as
 * plain FormData. Decomposed into focused children: the time-frame control and the scenario presets.
 *
 * Scenario seeds + corpus come from the workspace manifest (passed by the server page) — there is no
 * hand-maintained scenario list.
 */
export function Composer({ manifest }: { manifest: Manifest | null }) {
  const [query, setQuery] = useState("");
  const [scenario, setScenario] = useState(""); // selected preset id, "" = none
  const [frame, setFrame] = useState<FrameInput>(INITIAL_FRAME);

  const scenarios = manifest?.scenarios ?? [];

  // A preset fills the report + the frame in one go. Any later manual edit clears the selection
  // (the run is no longer "the preset's frame"), but keeps whatever the user typed.
  function selectPreset(seed: ScenarioSeed) {
    setQuery(seed.query);
    setFrame(frameFromSeed(seed));
    setScenario(seed.id);
  }

  return (
    <Card>
      <CardContent>
        <form action={createInvestigation} className="space-y-3">
          {/* hidden fields carry component state into the server action's FormData */}
          <input type="hidden" name="scenario" value={scenario} />
          <input type="hidden" name="mode" value={frame.mode} />
          <input type="hidden" name="as_of" value={frame.asOf ?? ""} />
          <input type="hidden" name="look_back" value={frame.lookBack ?? ""} />
          <input type="hidden" name="since" value={frame.since ?? ""} />
          <input type="hidden" name="until" value={frame.until ?? ""} />

          <Textarea
            name="query"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setScenario("");
            }}
            placeholder="Describe the incident… e.g. checkout is throwing 504s and customers are complaining"
            rows={2}
            required
          />

          <TimeFrameControl
            frame={frame}
            onChange={(next) => {
              setFrame(next);
              setScenario("");
            }}
            corpus={manifest?.corpus}
          />

          <ScenarioPresets scenarios={scenarios} selected={scenario} onSelect={selectPreset} />

          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Workspace</span>
              <Select name="workspace" defaultValue={manifest?.workspace ?? "acme-checkout"}>
                <SelectTrigger size="sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={manifest?.workspace ?? "acme-checkout"}>
                    {manifest?.workspace ?? "acme-checkout"}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <SubmitButton />
          </div>

          <details className="text-xs text-muted-foreground">
            <summary className="cursor-pointer select-none hover:text-foreground">Advanced</summary>
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <label className="flex items-center gap-2">
                Model
                <Input name="model" defaultValue="gemini-3.1-flash-lite" className="h-7 w-56" />
              </label>
              <label className="flex items-center gap-2">
                Max steps
                <Input name="max_steps" type="number" defaultValue={12} min={1} max={30} className="h-7 w-20" />
              </label>
            </div>
          </details>
        </form>
      </CardContent>
    </Card>
  );
}
