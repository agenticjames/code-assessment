import { notFound } from "next/navigation";

import { LiveRun } from "@/components/investigations/live-run";
import { customerImpactSchema, statusCheckSchema } from "@/lib/contracts";
import { getInvestigation } from "@/lib/db/queries";

export const dynamic = "force-dynamic";

export default async function InvestigationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const row = await getInvestigation(id);
  if (!row) notFound();

  // The deterministic comms-pass artifacts live on the ledger (like grounding). Parse defensively —
  // older runs (or a run still in flight) won't have them yet.
  const ledger = (row.ledgerJson ?? {}) as { impact?: unknown; status_check?: unknown };
  const impact = customerImpactSchema.safeParse(ledger.impact);
  const statusCheck = statusCheckSchema.safeParse(ledger.status_check);

  return (
    <div className="mx-auto w-full max-w-5xl">
      <LiveRun
        initial={{
          id: row.id,
          query: row.query,
          workspace: row.workspace,
          scenario: row.scenario,
          model: row.model,
          status: row.status,
          groundingVerified: row.groundingVerified,
          groundingTotal: row.groundingTotal,
          windowStart: row.windowStart,
          windowEnd: row.windowEnd,
          impact: impact.success ? impact.data : null,
          statusCheck: statusCheck.success ? statusCheck.data : null,
        }}
      />
    </div>
  );
}
