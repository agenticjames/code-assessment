"use server";

/**
 * Server actions — the only mutations in the app (docs/PHASE2.md §4.6).
 * createInvestigation: validate -> INSERT (Postgres) -> XADD (Redis) -> redirect.
 * cancelInvestigation: SET the Redis cancel flag the worker checks between steps.
 */
import { randomUUID } from "node:crypto";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { jobSchema } from "@/lib/contracts";
import { db } from "@/lib/db/client";
import { investigations } from "@/lib/db/schema";
import { env } from "@/lib/env";
import { cancelKey, JOBS_STREAM, redis } from "@/lib/redis";
import { previewWindow, type FrameInput, type FrameMode } from "@/lib/timeframe";

const DEFAULT_PROVIDER = "google_genai";
const DEFAULT_MODEL = "gemini-3.1-flash-lite";
const DEFAULT_MAX_STEPS = 12;

export async function createInvestigation(formData: FormData): Promise<void> {
  const query = String(formData.get("query") ?? "").trim();
  if (!query) throw new Error("A query is required.");

  const field = (key: string): string | null =>
    String(formData.get(key) ?? "").trim() || null;

  const workspace = String(formData.get("workspace") || env.WORKSPACE_DEFAULT);
  const scenario = field("scenario");
  const model = String(formData.get("model") || DEFAULT_MODEL);
  const maxSteps = Number(formData.get("max_steps")) || DEFAULT_MAX_STEPS;

  // Time-frame inputs (raw; the engine's resolve_frame turns these into the authoritative window).
  const asOf = field("as_of");
  const lookBack = field("look_back");
  const since = field("since");
  const until = field("until");
  const mode: FrameMode = field("mode") === "retrospective" ? "retrospective" : "live";

  const id = randomUUID();
  // Validate the exact wire shape the worker will parse (fail fast, in one place).
  const job = jobSchema.parse({
    id,
    query,
    workspace,
    scenario,
    as_of: asOf,
    look_back: lookBack,
    since,
    until,
    provider: DEFAULT_PROVIDER,
    model,
    max_steps: maxSteps,
  });

  // Seed the frame columns only when the user gave an explicit frame — for a scenario-only or
  // default run the worker writes the authoritative window at finish. (Preview math only.)
  const frame: FrameInput = {
    mode,
    asOf: asOf ?? undefined,
    lookBack: lookBack ?? undefined,
    since: since ?? undefined,
    until: until ?? undefined,
  };
  const win = asOf || lookBack || since || until ? previewWindow(frame) : null;

  await db.insert(investigations).values({
    id,
    status: "queued",
    workspace,
    scenario,
    query,
    provider: DEFAULT_PROVIDER,
    model,
    maxSteps,
    asOf: asOf ? new Date(asOf) : win ? win[1] : null,
    windowStart: win ? win[0] : null,
    windowEnd: win ? win[1] : null,
  });
  await redis.xadd(JOBS_STREAM, "*", "data", JSON.stringify(job));

  redirect(`/investigations/${id}`);
}

export async function cancelInvestigation(id: string): Promise<void> {
  await redis.set(cancelKey(id), "1", "EX", 3600);
  revalidatePath(`/investigations/${id}`);
}
