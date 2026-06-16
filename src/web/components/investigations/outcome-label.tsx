import { outcomeLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

export function OutcomeLabel({
  outcome,
  className,
}: {
  outcome: string | null | undefined;
  className?: string;
}) {
  if (!outcome) return null;
  return (
    <span
      className={cn(
        "text-xs font-medium",
        outcome === "root_cause" ? "text-success" : "text-warning",
        className,
      )}
    >
      {outcomeLabel(outcome)}
    </span>
  );
}
