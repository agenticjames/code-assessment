import Link from "next/link";

import { CancelButton } from "./cancel-button";
import { GroundingBadge } from "./grounding-badge";
import { StatusBadge } from "./status-badge";

export function RunHeader({
  id,
  query,
  workspace,
  scenario,
  model,
  status,
  groundingVerified,
  groundingTotal,
}: {
  id: string;
  query: string;
  workspace: string;
  scenario: string | null;
  model: string;
  status: string;
  groundingVerified: number | null;
  groundingTotal: number | null;
}) {
  return (
    <div>
      <Link href="/investigations" className="text-xs text-muted-foreground hover:underline">
        ‹ Investigations
      </Link>
      <div className="mt-1 flex items-start justify-between gap-3">
        <h1 className="text-base font-medium">{query}</h1>
        <div className="flex shrink-0 items-center gap-2">
          <StatusBadge status={status} />
          <GroundingBadge verified={groundingVerified} total={groundingTotal} />
          {(status === "running" || status === "queued") && <CancelButton id={id} />}
        </div>
      </div>
      <div className="mt-1 flex flex-wrap gap-x-2 text-xs text-muted-foreground">
        <span>{workspace}</span>
        {scenario && <span>· Scenario {scenario}</span>}
        <span>· {model}</span>
      </div>
    </div>
  );
}
