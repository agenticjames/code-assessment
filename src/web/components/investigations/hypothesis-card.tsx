import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { Hypothesis } from "@/lib/contracts";
import { cn } from "@/lib/utils";

import { ConfidenceBar } from "./confidence-bar";
import { EvidenceList } from "./evidence-list";

type StatusStyle = {
  label: string;
  variant: "success" | "destructive" | "secondary";
  tone: "success" | "muted" | "warning";
  ring: string;
};

const STATUS: Record<string, StatusStyle> = {
  confirmed: { label: "confirmed", variant: "success", tone: "success", ring: "ring-success/30" },
  ruled_out: { label: "ruled out", variant: "destructive", tone: "muted", ring: "ring-destructive/20" },
  open: { label: "open", variant: "secondary", tone: "warning", ring: "ring-foreground/10" },
};

/** Mirrors cli/render.py `_hypothesis_panel`. */
export function HypothesisCard({ hypothesis: h, rank }: { hypothesis: Hypothesis; rank: number }) {
  const s = STATUS[h.status] ?? STATUS.open;
  return (
    <Card className={cn("gap-3", s.ring)}>
      <CardContent className="space-y-2.5">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs text-muted-foreground">{h.id || `H${rank}`}</span>
            {h.service && (
              <Badge variant="info" className="font-mono">
                {h.service}
              </Badge>
            )}
            <Badge variant={s.variant}>{s.label}</Badge>
          </div>
          <p className="text-sm font-medium leading-snug">{h.statement}</p>
        </div>

        <ConfidenceBar value={h.confidence} tone={s.tone} />

        {h.status === "ruled_out" && h.ruled_out_reason && (
          <p className="text-xs text-muted-foreground">
            <span className="text-destructive">ruled out:</span> {h.ruled_out_reason}
          </p>
        )}

        {h.supporting?.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Supporting</p>
            <EvidenceList refs={h.supporting} borderClass="border-success/40" />
          </div>
        )}
        {h.contradicting?.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Contradicting</p>
            <EvidenceList refs={h.contradicting} borderClass="border-destructive/40" />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
