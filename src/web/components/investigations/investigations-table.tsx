import Link from "next/link";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { InvestigationRow } from "@/lib/db/schema";
import { relativeTime } from "@/lib/format";

import { ConfidenceBar } from "./confidence-bar";
import { GroundingBadge } from "./grounding-badge";
import { StatusBadge } from "./status-badge";

export function InvestigationsTable({ rows }: { rows: InvestigationRow[] }) {
  if (!rows.length) {
    return (
      <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
        No investigations yet — start one above.
      </p>
    );
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-28">Status</TableHead>
          <TableHead>Query</TableHead>
          <TableHead>Top hypothesis</TableHead>
          <TableHead className="w-32">Confidence</TableHead>
          <TableHead>Grounded</TableHead>
          <TableHead className="w-20">When</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.id}>
            <TableCell>
              <StatusBadge status={r.status} />
            </TableCell>
            <TableCell className="max-w-[22rem]">
              <Link href={`/investigations/${r.id}`} className="block truncate hover:underline">
                {r.query}
              </Link>
              {r.scenario && (
                <span className="font-mono text-[10px] text-muted-foreground">[{r.scenario}]</span>
              )}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {r.topService ?? (r.status === "running" ? "analyzing…" : "—")}
            </TableCell>
            <TableCell>
              {r.topConfidence != null ? (
                <ConfidenceBar value={r.topConfidence} />
              ) : (
                <span className="text-muted-foreground">—</span>
              )}
            </TableCell>
            <TableCell>
              <GroundingBadge verified={r.groundingVerified} total={r.groundingTotal} />
            </TableCell>
            <TableCell className="text-muted-foreground">{relativeTime(r.createdAt)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
