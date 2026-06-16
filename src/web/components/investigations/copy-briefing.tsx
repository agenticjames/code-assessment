"use client";

import { Copy } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import type { InvestigationResult } from "@/lib/contracts";

/** Copy a stakeholder-ready update. Prefers the engine's `stakeholder_note` (the single source of
 * truth, written from the evidence); falls back to assembling one from the verdict for older runs
 * that predate the field — never fabricates beyond what the engine emitted. */
export function CopyBriefing({ result }: { result: InvestigationResult }) {
  const onCopy = async () => {
    const top = [...result.hypotheses].sort((a, b) => b.confidence - a.confidence)[0];
    const text = result.stakeholder_note
      ? result.stakeholder_note
      : [
          `Incident: ${result.query}`,
          `Summary: ${result.summary}`,
          top
            ? `Likely cause: ${top.statement} (${Math.round(top.confidence * 100)}% confidence)`
            : "",
          result.recommended_action ? `Recommended action: ${result.recommended_action}` : "",
        ]
          .filter(Boolean)
          .join("\n");
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Briefing copied to clipboard");
    } catch {
      toast.error("Couldn't copy to clipboard");
    }
  };

  return (
    <Button variant="outline" size="sm" onClick={onCopy}>
      <Copy /> Copy
    </Button>
  );
}
