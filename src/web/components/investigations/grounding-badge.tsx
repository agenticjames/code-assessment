import { Badge } from "@/components/ui/badge";

export function GroundingBadge({
  verified,
  total,
  className,
}: {
  verified: number | null | undefined;
  total: number | null | undefined;
  className?: string;
}) {
  if (total == null || verified == null || total === 0) return null;
  const clean = verified === total;
  return (
    <Badge variant={clean ? "success" : "warning"} className={className}>
      {clean ? "✓" : "!"} {verified}/{total} verified
    </Badge>
  );
}
