"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useEventStream } from "@/hooks/use-event-stream";
import type { CustomerImpact, InvestigationResult, StatusCheck, TraceEvent } from "@/lib/contracts";

import { BlastRadius } from "./blast-radius";
import { Briefing } from "./briefing";
import { CustomerImpactCard } from "./customer-impact";
import { RunHeader } from "./run-header";
import { SourceViewerProvider } from "./source-viewer";
import { StatusCorrection } from "./status-correction";
import { ToolCallAudit } from "./tool-call-audit";
import { TracePanel } from "./trace-panel";

export type LiveRunInitial = {
  id: string;
  query: string;
  workspace: string;
  scenario: string | null;
  model: string;
  status: string;
  groundingVerified: number | null;
  groundingTotal: number | null;
  // The resolved incident window (persisted columns); null until seeded/finished.
  windowStart?: string | Date | null;
  windowEnd?: string | Date | null;
  // Deterministic comms-pass artifacts (from ledger_json); null until the run completes.
  impact?: CustomerImpact | null;
  statusCheck?: StatusCheck | null;
};

const TRACE_TYPES = new Set([
  "scenario",
  "phase",
  "hypotheses",
  "tool_call",
  "tool_result",
  "thinking_done",
  "budget_exhausted",
  "error",
]);

/**
 * The detail orchestrator. ONE path drives both live and completed runs: the SSE stream replays the
 * durable events for a finished run and tails Redis for a live one. We reduce the event list into the
 * run's current view (status / verdict / grounding / trace).
 */
export function LiveRun({ initial }: { initial: LiveRunInitial }) {
  const router = useRouter();
  const { events, done } = useEventStream(initial.id, true);

  // The comms-pass panels (customer impact / status correction) live on the ledger and are read ONCE
  // by the RSC at page-load — they are NOT carried in the trace stream. If we opened the page mid-run,
  // that snapshot has no impact yet, so refresh the RSC once the run finishes to pull them in (rather
  // than forcing a manual reload). A page opened on an already-finished run already has them.
  const loadedLive = initial.status === "queued" || initial.status === "running";
  const refreshed = useRef(false);
  useEffect(() => {
    if (done && loadedLive && !refreshed.current) {
      refreshed.current = true;
      router.refresh();
    }
  }, [done, loadedLive, router]);

  const run = useMemo(() => {
    let status = initial.status;
    let verdict: InvestigationResult | null = null;
    let grounding =
      initial.groundingTotal != null
        ? { verified: initial.groundingVerified ?? 0, total: initial.groundingTotal }
        : null;
    let error: string | null = null;
    const trace: TraceEvent[] = [];
    for (const ev of events) {
      if (ev.type === "status") status = "running";
      else if (ev.type === "done") status = ev.data.status;
      else if (ev.type === "verdict") verdict = ev.data;
      else if (ev.type === "grounding") grounding = ev.data;
      else if (ev.type === "error") {
        error = ev.data.message;
        trace.push(ev);
      } else if (TRACE_TYPES.has(ev.type)) trace.push(ev);
    }
    return { status, verdict, grounding, trace, error };
  }, [events, initial.status, initial.groundingVerified, initial.groundingTotal]);

  const running = run.status === "running" || run.status === "queued";

  return (
    <SourceViewerProvider workspace={initial.workspace}>
      <div className="space-y-5">
        <RunHeader
          id={initial.id}
          query={initial.query}
          workspace={initial.workspace}
          scenario={initial.scenario}
          model={initial.model}
          status={run.status}
          groundingVerified={run.grounding?.verified ?? null}
          groundingTotal={run.grounding?.total ?? null}
          windowStart={initial.windowStart}
          windowEnd={initial.windowEnd}
        />

        <Tabs defaultValue="briefing" className="w-full">
          <TabsList variant="line">
            <TabsTrigger value="briefing">Briefing</TabsTrigger>
            <TabsTrigger value="trace">Reasoning trace</TabsTrigger>
            <TabsTrigger value="tools">Tool calls</TabsTrigger>
            <TabsTrigger value="graph">Blast radius</TabsTrigger>
          </TabsList>

          <TabsContent value="briefing">
            {run.verdict ? (
              <div className="space-y-4">
                <CustomerImpactCard impact={initial.impact} />
                <Briefing result={run.verdict} />
                <StatusCorrection check={initial.statusCheck} />
              </div>
            ) : run.status === "failed" ? (
              <p className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
                {run.error ?? "Investigation failed."}
              </p>
            ) : (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span className="size-2 animate-pulse rounded-full bg-warning" />
                {running
                  ? "Investigating… the briefing resolves when adjudication completes."
                  : "No briefing was produced."}
              </div>
            )}
          </TabsContent>

          <TabsContent value="trace">
            <TracePanel events={run.trace} running={running && !done} />
          </TabsContent>

          <TabsContent value="tools">
            <ToolCallAudit events={run.trace} />
          </TabsContent>

          <TabsContent value="graph">
            {run.verdict ? (
              <BlastRadius workspace={initial.workspace} hypotheses={run.verdict.hypotheses} />
            ) : (
              <p className="text-sm text-muted-foreground">Available once the verdict resolves.</p>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </SourceViewerProvider>
  );
}
