import { notFound } from "next/navigation";

import { LiveRun } from "@/components/investigations/live-run";
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
        }}
      />
    </div>
  );
}
