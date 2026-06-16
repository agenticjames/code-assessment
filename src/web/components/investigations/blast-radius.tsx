"use client";

import { useEffect, useMemo, useState } from "react";

import type { Hypothesis } from "@/lib/contracts";
import { cn } from "@/lib/utils";

import { buildGraph, NODE_H, NODE_W, type Topology } from "./blast-radius.graph";

/**
 * Blast-radius graph (docs/PHASE2.md §6): the dependency subgraph around the implicated services,
 * with the confirmed cause lit and the ruled-out herring greyed/struck. The visible payoff of the
 * in-memory topology graph. Layout math lives in {@link buildGraph}.
 */
export function BlastRadius({
  workspace,
  hypotheses,
}: {
  workspace: string;
  hypotheses: Hypothesis[];
}) {
  const [topo, setTopo] = useState<Topology | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let alive = true;
    fetch(`/api/topology?workspace=${encodeURIComponent(workspace)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("topology"))))
      .then((d) => alive && setTopo(d))
      .catch(() => alive && setErr(true));
    return () => {
      alive = false;
    };
  }, [workspace]);

  const graph = useMemo(() => (topo ? buildGraph(topo, hypotheses) : null), [topo, hypotheses]);

  if (err) return <Msg>Topology unavailable.</Msg>;
  if (!graph) return <Msg>Loading topology…</Msg>;
  if (!graph.nodes.length) return <Msg>No services implicated.</Msg>;

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${graph.width} ${graph.height}`}
          width={graph.width}
          height={graph.height}
          role="img"
          aria-label={`Dependency blast radius — ${graph.nodes.length} services around the incident`}
          className="max-w-full"
        >
          {graph.edges.map((e, i) => (
            <line
              key={i}
              x1={e.x1}
              y1={e.y1}
              x2={e.x2}
              y2={e.y2}
              className={e.cause ? "stroke-success" : "stroke-border"}
              strokeWidth={e.cause ? 2 : 1}
            />
          ))}
          {graph.nodes.map((n) => (
            <g key={n.name} transform={`translate(${n.x},${n.y})`}>
              <rect
                width={NODE_W}
                height={NODE_H}
                rx={7}
                className={cn(
                  "fill-card",
                  n.role === "cause"
                    ? "stroke-success"
                    : n.role === "cleared"
                      ? "stroke-muted-foreground"
                      : "stroke-border",
                )}
                strokeWidth={n.role === "cause" ? 2 : 1}
                strokeDasharray={n.role === "cleared" ? "4 3" : undefined}
              />
              <text
                x={NODE_W / 2}
                y={NODE_H / 2 + 4}
                textAnchor="middle"
                className={cn(
                  "font-mono text-[11px]",
                  n.role === "cleared" ? "fill-muted-foreground" : "fill-foreground",
                )}
                style={n.role === "cleared" ? { textDecoration: "line-through" } : undefined}
              >
                {n.name}
              </text>
            </g>
          ))}
        </svg>
      </div>
      <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
        <Legend className="bg-success" label="confirmed cause" />
        <Legend className="border border-dashed border-muted-foreground" label="ruled out" />
        <Legend className="border border-border bg-card" label="dependency" />
      </div>
    </div>
  );
}

function Legend({ className, label }: { className: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn("size-3 rounded-sm", className)} aria-hidden />
      {label}
    </span>
  );
}

function Msg({ children }: { children: React.ReactNode }) {
  return <p className="rounded-lg border p-4 text-sm text-muted-foreground">{children}</p>;
}
