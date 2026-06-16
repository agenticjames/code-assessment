import type { Hypothesis } from "@/lib/contracts";

export type Topology = Record<string, { tier?: string; depends_on?: string[] }>;
export type Role = "cause" | "cleared" | "neutral";
export type GraphNode = { name: string; x: number; y: number; role: Role };
export type GraphEdge = { x1: number; y1: number; x2: number; y2: number; cause: boolean };
export type GraphLayout = { nodes: GraphNode[]; edges: GraphEdge[]; width: number; height: number };

export const TIERS = ["edge", "core", "platform", "data", "external"];
export const NODE_W = 118;
export const NODE_H = 32;
const COL_W = 152;
const ROW_H = 56;
const PAD_X = 12;
const PAD_Y = 16;
const MAX_NODES = 14;

/**
 * Build the blast-radius layout from the topology + the verdict's hypotheses.
 *
 * The "relevant" subgraph is: each hypothesis' implicated `service`, its direct `depends_on`
 * dependencies, and any service that *shares* one of those dependencies — i.e. the incident's
 * dependency neighbourhood. Nodes are placed in tier columns (edge → external, left → right) so
 * `depends_on` edges run rightward; the confirmed cause is flagged `cause` and ruled-out herrings
 * `cleared`. Capped at {@link MAX_NODES} to stay legible.
 *
 * Pure + deterministic (no I/O) — unit-testable in isolation.
 */
export function buildGraph(topo: Topology, hypotheses: Hypothesis[]): GraphLayout {
  const cause = new Set(
    hypotheses.filter((h) => h.status === "confirmed" && h.service).map((h) => h.service as string),
  );
  const cleared = new Set(
    hypotheses.filter((h) => h.status === "ruled_out" && h.service).map((h) => h.service as string),
  );
  const seeds = hypotheses.map((h) => h.service).filter((s): s is string => !!s);

  const relevant = new Set<string>(seeds.filter((s) => topo[s]));
  const deps = new Set<string>();
  for (const s of seeds) for (const d of topo[s]?.depends_on ?? []) deps.add(d);
  for (const d of deps) if (topo[d]) relevant.add(d);
  for (const [svc, info] of Object.entries(topo)) {
    if ((info.depends_on ?? []).some((d) => deps.has(d))) relevant.add(svc);
  }

  const names = [...relevant].filter((n) => topo[n]).slice(0, MAX_NODES);

  const byTier = new Map<string, string[]>(TIERS.map((t) => [t, []]));
  for (const n of names) {
    const tier = topo[n]?.tier;
    byTier.get(tier && byTier.has(tier) ? tier : "core")!.push(n);
  }
  const usedTiers = TIERS.filter((t) => (byTier.get(t)?.length ?? 0) > 0);
  const colOf = new Map(usedTiers.map((t, i) => [t, i]));

  const pos = new Map<string, { x: number; y: number }>();
  for (const t of usedTiers) {
    byTier.get(t)!.forEach((n, ri) => {
      pos.set(n, { x: PAD_X + (colOf.get(t) ?? 0) * COL_W, y: PAD_Y + ri * ROW_H });
    });
  }

  const maxRows = Math.max(1, ...usedTiers.map((t) => byTier.get(t)!.length));
  const width = PAD_X * 2 + Math.max(0, usedTiers.length - 1) * COL_W + NODE_W;
  const height = PAD_Y * 2 + (maxRows - 1) * ROW_H + NODE_H;

  const nodes: GraphNode[] = names.map((n) => ({
    name: n,
    x: pos.get(n)!.x,
    y: pos.get(n)!.y,
    role: cause.has(n) ? "cause" : cleared.has(n) ? "cleared" : "neutral",
  }));

  const edges: GraphEdge[] = [];
  for (const n of names) {
    for (const d of topo[n]?.depends_on ?? []) {
      if (!pos.has(d)) continue;
      const a = pos.get(n)!;
      const b = pos.get(d)!;
      edges.push({
        x1: a.x + NODE_W,
        y1: a.y + NODE_H / 2,
        x2: b.x,
        y2: b.y + NODE_H / 2,
        cause: cause.has(n),
      });
    }
  }

  return { nodes, edges, width, height };
}
