"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useFormStatus } from "react-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { createInvestigation } from "@/lib/actions";
import { SCENARIOS } from "@/lib/scenarios";

function SubmitButton() {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" disabled={pending}>
      {pending ? (
        <>
          <Loader2 className="animate-spin" /> Investigating…
        </>
      ) : (
        "Investigate"
      )}
    </Button>
  );
}

export function Composer() {
  const [query, setQuery] = useState("");
  const [scenario, setScenario] = useState("");

  return (
    <Card>
      <CardContent>
        <form action={createInvestigation} className="space-y-3">
          <input type="hidden" name="scenario" value={scenario} />

          <Textarea
            name="query"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setScenario("");
            }}
            placeholder="Describe the incident… e.g. checkout is throwing 504s and customers are complaining"
            rows={2}
            required
          />

          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-muted-foreground">or from a scenario:</span>
            {SCENARIOS.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => {
                  setQuery(s.query);
                  setScenario(s.id);
                }}
                className="cursor-pointer"
              >
                <Badge variant={scenario === s.id ? "default" : "outline"}>
                  {s.id} · {s.label}
                </Badge>
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Workspace</span>
              <Select name="workspace" defaultValue="acme-checkout">
                <SelectTrigger size="sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="acme-checkout">acme-checkout</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <SubmitButton />
          </div>

          <details className="text-xs text-muted-foreground">
            <summary className="cursor-pointer select-none hover:text-foreground">Advanced</summary>
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <label className="flex items-center gap-2">
                Model
                <Input name="model" defaultValue="gemini-3.1-flash-lite" className="h-7 w-56" />
              </label>
              <label className="flex items-center gap-2">
                Max steps
                <Input name="max_steps" type="number" defaultValue={12} min={1} max={30} className="h-7 w-20" />
              </label>
            </div>
          </details>
        </form>
      </CardContent>
    </Card>
  );
}
