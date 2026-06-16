/**
 * Demo scenario quick-picks for the composer. The canonical source is each scenario's query.yaml;
 * this small seed list powers the picker chips (it mirrors workspaces/acme-checkout/README.md).
 */
export type ScenarioSeed = { id: string; label: string; query: string };

export const SCENARIOS: ScenarioSeed[] = [
  { id: "A", label: "504s", query: "checkout is throwing 504s and customers are complaining" },
  { id: "B", label: "alert storm", query: "we're getting paged by ~20 alerts, what's actually going on?" },
  { id: "C", label: "intermittent", query: "intermittent 500s for the last hour, can't reproduce" },
  { id: "D", label: "recurring", query: "orders failing with connection errors again" },
  { id: "E", label: "deploy", query: "error rate spiked right after this morning's deploy" },
  { id: "F", label: "slow burn", query: "checkout getting slower over the past few days" },
  { id: "G", label: "retro range", query: "why was checkout unstable between June 10 and June 12?" },
];
