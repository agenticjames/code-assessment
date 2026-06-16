"use client";

import type { EvidenceRef } from "@/lib/contracts";
import { cn } from "@/lib/utils";

import { useSourceViewer } from "./source-viewer";

/** A clickable `path:line` evidence chip with the verify tick — opens the source viewer at the line. */
export function Citation({ evidence, className }: { evidence: EvidenceRef; className?: string }) {
  const { open } = useSourceViewer();
  return (
    <button
      type="button"
      onClick={() => open(evidence.source)}
      title={evidence.snippet}
      className={cn(
        "inline-flex items-center gap-1 rounded bg-info/10 px-1.5 py-0.5 align-middle font-mono text-[11px] text-info transition-colors hover:bg-info/20",
        className,
      )}
    >
      {evidence.source}
      {evidence.verified === true && (
        <span className="text-success" aria-label="verified">
          ✓
        </span>
      )}
      {evidence.verified === false && (
        <span className="text-destructive" aria-label="unverified">
          ✗
        </span>
      )}
    </button>
  );
}
