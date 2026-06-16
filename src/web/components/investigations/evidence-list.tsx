import type { EvidenceRef } from "@/lib/contracts";
import { cn } from "@/lib/utils";

import { Citation } from "./citation";

export function EvidenceList({
  refs,
  borderClass = "border-border",
}: {
  refs: EvidenceRef[];
  borderClass?: string;
}) {
  if (!refs?.length) return null;
  return (
    <ul className="space-y-1.5">
      {refs.map((e, i) => (
        <li
          key={i}
          className={cn("border-l-2 pl-2.5 text-xs leading-relaxed text-muted-foreground", borderClass)}
        >
          <span className="text-foreground">{e.claim}</span> <Citation evidence={e} />
        </li>
      ))}
    </ul>
  );
}
