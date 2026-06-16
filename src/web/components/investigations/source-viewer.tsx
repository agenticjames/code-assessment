"use client";

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

type SourceData = { path: string; lines: string[]; line: number | null };
type Ctx = { open: (source: string) => void };

// Default no-op so a <Citation> renders safely even outside a provider.
const SourceViewerContext = createContext<Ctx>({ open: () => {} });
export const useSourceViewer = () => useContext(SourceViewerContext);

/**
 * Holds the source-viewer drawer and exposes `open(source)` via context, so any citation deep in the
 * briefing tree can open the cited file at its line — the web payoff of the deterministic verifier.
 */
export function SourceViewerProvider({
  workspace,
  children,
}: {
  workspace: string;
  children: ReactNode;
}) {
  const [source, setSource] = useState<string | null>(null);
  const [data, setData] = useState<SourceData | null>(null);
  const [loading, setLoading] = useState(false);

  const open = useCallback(
    async (src: string) => {
      setSource(src);
      setData(null);
      setLoading(true);
      const [p, lineStr] = src.split(":");
      const params = new URLSearchParams({ workspace, path: p });
      if (lineStr) params.set("line", lineStr);
      try {
        const res = await fetch(`/api/source?${params.toString()}`);
        if (res.ok) setData(await res.json());
      } catch {
        /* leave data null → "not available" */
      } finally {
        setLoading(false);
      }
    },
    [workspace],
  );

  return (
    <SourceViewerContext.Provider value={{ open }}>
      {children}
      <Sheet
        open={source != null}
        onOpenChange={(o: boolean) => {
          if (!o) setSource(null);
        }}
      >
        <SheetContent side="right" className="!w-[min(92vw,46rem)] gap-0 sm:!max-w-[46rem]">
          <SheetHeader className="border-b">
            <SheetTitle className="font-mono text-sm break-all">{source}</SheetTitle>
            <SheetDescription>Source evidence — read-only, access-bounded to the workspace.</SheetDescription>
          </SheetHeader>
          <div className="min-h-0 flex-1 overflow-auto p-4">
            {loading && <p className="text-sm text-muted-foreground">Loading…</p>}
            {!loading && data && <SourceCode lines={data.lines} highlight={data.line} />}
            {!loading && !data && <p className="text-sm text-muted-foreground">Source not available.</p>}
          </div>
        </SheetContent>
      </Sheet>
    </SourceViewerContext.Provider>
  );
}

function SourceCode({ lines, highlight }: { lines: string[]; highlight: number | null }) {
  const start = highlight ? Math.max(0, highlight - 8) : 0;
  const end = highlight ? Math.min(lines.length, highlight + 8) : Math.min(lines.length, 50);
  return (
    <pre className="overflow-x-auto rounded-lg bg-muted/40 p-3 font-mono text-xs leading-relaxed">
      {lines.slice(start, end).map((l, i) => {
        const n = start + i + 1;
        return (
          <div key={n} className={cn("flex gap-3", n === highlight && "-mx-3 rounded bg-warning/20 px-3")}>
            <span className="w-8 shrink-0 text-right text-muted-foreground select-none">{n}</span>
            <span className="whitespace-pre">{l || " "}</span>
          </div>
        );
      })}
    </pre>
  );
}
