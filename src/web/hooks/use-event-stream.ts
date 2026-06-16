"use client";

import { useEffect, useRef, useState } from "react";

import { traceEventSchema, type TraceEvent } from "@/lib/contracts";

/**
 * Subscribes to the SSE trace stream and accumulates validated events (deduped by seq). The browser
 * auto-reconnects with Last-Event-ID on a dropped connection; we close on the terminal `done`.
 */
export function useEventStream(id: string, enabled: boolean) {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [done, setDone] = useState(false);
  const seen = useRef<Set<number>>(new Set());

  useEffect(() => {
    if (!enabled) return;
    // Each investigation is a separate route → fresh mount → fresh state; no reset needed here.
    const es = new EventSource(`/api/investigations/${id}/events`);
    es.onmessage = (e) => {
      let raw: unknown;
      try {
        raw = JSON.parse(e.data);
      } catch {
        return;
      }
      const parsed = traceEventSchema.safeParse(raw);
      if (!parsed.success || seen.current.has(parsed.data.seq)) return;
      seen.current.add(parsed.data.seq);
      setEvents((prev) => [...prev, parsed.data]);
      if (parsed.data.type === "done") {
        setDone(true);
        es.close();
      }
    };
    es.onerror = () => {
      /* EventSource reconnects automatically with Last-Event-ID */
    };
    return () => es.close();
  }, [id, enabled]);

  return { events, done };
}
