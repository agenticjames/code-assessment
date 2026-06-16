"use client";

import { Loader2, XCircle } from "lucide-react";
import { useTransition } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { cancelInvestigation } from "@/lib/actions";

export function CancelButton({ id }: { id: string }) {
  const [pending, start] = useTransition();
  return (
    <Button
      variant="destructive"
      size="sm"
      disabled={pending}
      onClick={() =>
        start(async () => {
          await cancelInvestigation(id);
          toast("Cancellation requested");
        })
      }
    >
      {pending ? <Loader2 className="animate-spin" /> : <XCircle />} Cancel
    </Button>
  );
}
