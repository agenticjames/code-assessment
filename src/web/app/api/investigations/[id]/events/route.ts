import { and, asc, eq, gt } from "drizzle-orm";

import { db } from "@/lib/db/client";
import { traceEvents } from "@/lib/db/schema";
import { redis, traceKey } from "@/lib/redis";

// SSE needs the long-lived Node runtime (not edge/serverless).
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const TERMINAL = "done";

/**
 * Live trace stream (docs/PHASE2.md §1): replay the durable events from Postgres (so a reload or
 * late-join sees the whole run), then tail the Redis stream for live events until the terminal
 * `done`. Honors `Last-Event-ID` (a seq) so a reconnect resumes without duplicates.
 */
export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const headerId = Number(req.headers.get("last-event-id"));
  const encoder = new TextEncoder();
  const state = { closed: false, sub: null as ReturnType<typeof redis.duplicate> | null };

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      let lastSeq = Number.isFinite(headerId) ? headerId : -1;

      const enqueue = (text: string) => {
        if (state.closed) return;
        try {
          controller.enqueue(encoder.encode(text));
        } catch {
          state.closed = true;
        }
      };
      const send = (ev: { seq: number; type: string }) =>
        enqueue(`id: ${ev.seq}\ndata: ${JSON.stringify(ev)}\n\n`);
      const finish = () => {
        if (state.closed) return;
        state.closed = true;
        try {
          controller.close();
        } catch {
          /* already closed */
        }
      };

      // 1) Replay durable events from Postgres.
      const persisted = await db
        .select()
        .from(traceEvents)
        .where(and(eq(traceEvents.investigationId, id), gt(traceEvents.seq, lastSeq)))
        .orderBy(asc(traceEvents.seq));
      for (const row of persisted) {
        send({ seq: row.seq, type: row.type, ...wrap(row) });
        lastSeq = row.seq;
        if (row.type === TERMINAL) return finish();
      }

      // 2) Tail the Redis live stream until the terminal `done`.
      const sub = redis.duplicate();
      state.sub = sub;
      try {
        let cursor = "0";
        while (!state.closed) {
          const res = (await sub.xread("BLOCK", 15000, "STREAMS", traceKey(id), cursor)) as
            | [string, [string, string[]][]][]
            | null;
          if (!res) {
            enqueue(`: keepalive\n\n`);
            continue;
          }
          for (const [, entries] of res) {
            for (const [entryId, fields] of entries) {
              cursor = entryId;
              const env = JSON.parse(fields[1]) as { seq: number; type: string };
              if (env.seq > lastSeq) {
                send(env);
                lastSeq = env.seq;
                if (env.type === TERMINAL) return finish();
              }
            }
          }
        }
      } catch {
        finish();
      } finally {
        sub.disconnect();
      }
    },
    cancel() {
      state.closed = true;
      state.sub?.disconnect();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}

// The stored row's payload is the event `data`; ts comes along for completeness.
function wrap(row: { ts: Date; payload: unknown }) {
  return { ts: row.ts.toISOString(), data: row.payload };
}
