"use client";

import { Button } from "@/components/ui/button";

/**
 * Error boundary for the investigations route segment (list + detail + their children). Catches
 * render/data errors — e.g. Postgres or Redis unreachable during an RSC read — and offers a retry
 * instead of crashing the app.
 */
export default function InvestigationsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-3 py-16 text-center">
      <h2 className="text-base font-medium">Something went wrong</h2>
      <p className="text-sm text-muted-foreground">
        {error.message || "An unexpected error occurred while loading investigations."}
      </p>
      <Button variant="outline" size="sm" onClick={reset}>
        Try again
      </Button>
    </div>
  );
}
