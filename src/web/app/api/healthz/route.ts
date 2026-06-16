import { sql } from "drizzle-orm";
import { NextResponse } from "next/server";

import { db } from "@/lib/db/client";
import { redis } from "@/lib/redis";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Liveness + dependency health (Postgres + Redis) for deploy probes. */
export async function GET() {
  const checks: Record<string, boolean> = {};
  try {
    await db.execute(sql`select 1`);
    checks.postgres = true;
  } catch {
    checks.postgres = false;
  }
  try {
    await redis.ping();
    checks.redis = true;
  } catch {
    checks.redis = false;
  }
  const ok = Object.values(checks).every(Boolean);
  return NextResponse.json({ ok, checks }, { status: ok ? 200 : 503 });
}
