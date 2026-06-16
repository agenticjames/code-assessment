import type { InvestigationResult } from "@/lib/contracts";

import { CopyBriefing } from "./copy-briefing";
import { HypothesisCard } from "./hypothesis-card";
import { OutcomeLabel } from "./outcome-label";

/** Mirrors cli/render.py `_briefing`: ranked hypotheses, open questions, noise dropped,
 * recommended action, stakeholder update. */
export function Briefing({ result }: { result: InvestigationResult }) {
  const ranked = [...result.hypotheses].sort((a, b) => b.confidence - a.confidence);
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-medium text-muted-foreground">Briefing</h2>
            <OutcomeLabel outcome={result.outcome} />
          </div>
          <CopyBriefing result={result} />
        </div>
        <p className="text-sm leading-relaxed">{result.summary}</p>
      </div>

      <div className="space-y-2">
        {ranked.map((h, i) => (
          <HypothesisCard key={h.id || i} hypothesis={h} rank={i + 1} />
        ))}
      </div>

      {result.open_questions?.length > 0 && (
        <div className="space-y-1">
          <h3 className="text-xs font-medium text-muted-foreground">Open questions</h3>
          <ul className="list-disc space-y-0.5 pl-4 text-xs text-muted-foreground">
            {result.open_questions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ul>
        </div>
      )}

      {result.noise_dropped?.length > 0 && (
        <div className="space-y-1">
          <h3 className="text-xs font-medium text-muted-foreground">
            Noise dropped <span className="font-normal">(considered, then dismissed)</span>
          </h3>
          <ul className="space-y-0.5 text-xs text-muted-foreground">
            {result.noise_dropped.map((n, i) => (
              <li key={i}>
                <span className="text-foreground">{n.item}</span>{" "}
                <span className="opacity-70">— {n.reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.recommended_action && (
        <div className="rounded-lg bg-info/10 p-3">
          <p className="text-[11px] font-medium tracking-wide text-info uppercase">Recommended action</p>
          <p className="mt-1 text-sm">{result.recommended_action}</p>
        </div>
      )}

      {result.stakeholder_note && (
        <div className="rounded-lg border bg-card p-3">
          <p className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
            Stakeholder update <span className="normal-case opacity-70">(paste-ready)</span>
          </p>
          <p className="mt-1 text-sm leading-relaxed">{result.stakeholder_note}</p>
        </div>
      )}
    </div>
  );
}
