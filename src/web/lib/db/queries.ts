/**
 * Typed reads for RSC first paint (docs/PHASE2.md §6). The only place SQL for the UI lives.
 */
import "server-only";

import { desc, eq } from "drizzle-orm";

import { db } from "./client";
import { investigations, toolCalls } from "./schema";

export async function listInvestigations(limit = 50) {
  return db
    .select()
    .from(investigations)
    .orderBy(desc(investigations.createdAt))
    .limit(limit);
}

export async function getInvestigation(id: string) {
  const [row] = await db
    .select()
    .from(investigations)
    .where(eq(investigations.id, id))
    .limit(1);
  return row ?? null;
}

export async function getToolCalls(id: string) {
  return db
    .select()
    .from(toolCalls)
    .where(eq(toolCalls.investigationId, id))
    .orderBy(toolCalls.step);
}
