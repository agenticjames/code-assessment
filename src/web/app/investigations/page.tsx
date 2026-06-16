import { Composer } from "@/components/investigations/composer";
import { InvestigationsHistory } from "@/components/investigations/investigations-history";
import { listInvestigations } from "@/lib/db/queries";

// Always read fresh from Postgres (a dashboard, not a static page).
export const dynamic = "force-dynamic";

export default async function InvestigationsPage() {
  const rows = await listInvestigations();
  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      <div>
        <h1 className="text-lg font-medium">Investigations</h1>
        <p className="text-sm text-muted-foreground">
          Trigger a run, watch it reason, review the history.
        </p>
      </div>
      <Composer />
      <div className="space-y-2">
        <h2 className="text-sm font-medium text-muted-foreground">Recent</h2>
        <InvestigationsHistory rows={rows} />
      </div>
    </div>
  );
}
