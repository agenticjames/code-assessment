"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import type { InvestigationRow } from "@/lib/db/schema";

import { InvestigationsTable } from "./investigations-table";

const FILTERS = [
  { key: "all", label: "All" },
  { key: "running", label: "Running" },
  { key: "succeeded", label: "Done" },
  { key: "failed", label: "Failed" },
] as const;

export function InvestigationsHistory({ rows }: { rows: InvestigationRow[] }) {
  const [filter, setFilter] = useState<string>("all");

  const filtered =
    filter === "all"
      ? rows
      : filter === "running"
        ? rows.filter((r) => r.status === "running" || r.status === "queued")
        : rows.filter((r) => r.status === filter);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setFilter(f.key)}
            className="cursor-pointer"
          >
            <Badge variant={filter === f.key ? "default" : "outline"}>{f.label}</Badge>
          </button>
        ))}
      </div>
      <InvestigationsTable rows={filtered} />
    </div>
  );
}
