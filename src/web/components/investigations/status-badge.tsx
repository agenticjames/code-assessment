import { Badge } from "@/components/ui/badge";
import { statusLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

type Variant = "secondary" | "warning" | "success" | "destructive" | "outline";

const MAP: Record<string, { variant: Variant; dot: string }> = {
  queued: { variant: "secondary", dot: "bg-muted-foreground" },
  running: { variant: "warning", dot: "bg-warning" },
  succeeded: { variant: "success", dot: "bg-success" },
  failed: { variant: "destructive", dot: "bg-destructive" },
  canceled: { variant: "outline", dot: "bg-muted-foreground" },
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const s = MAP[status] ?? MAP.queued;
  return (
    <Badge variant={s.variant} className={cn("gap-1.5", className)}>
      <span
        className={cn("size-1.5 rounded-full", s.dot, status === "running" && "animate-pulse")}
        aria-hidden
      />
      {statusLabel(status)}
    </Badge>
  );
}
