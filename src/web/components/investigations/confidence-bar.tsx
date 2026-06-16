import { confidencePct } from "@/lib/format";
import { cn } from "@/lib/utils";

const TONE: Record<string, string> = {
  success: "bg-success",
  warning: "bg-warning",
  muted: "bg-muted-foreground",
  info: "bg-info",
};

export function ConfidenceBar({
  value,
  tone = "success",
  showValue = true,
  className,
}: {
  value: number;
  tone?: keyof typeof TONE;
  showValue?: boolean;
  className?: string;
}) {
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
        <div
          className={cn("absolute inset-y-0 left-0 rounded-full transition-[width] duration-500", TONE[tone])}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showValue && (
        <span className="font-mono text-xs tabular-nums text-muted-foreground">{confidencePct(value)}</span>
      )}
    </div>
  );
}
