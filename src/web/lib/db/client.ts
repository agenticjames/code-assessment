/**
 * The pooled Postgres client + Drizzle instance. Server-only — never import from a client component.
 * Reads are done through lib/db/queries.ts; this module just owns the connection.
 */
import "server-only";

import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";

import { env } from "@/lib/env";
import * as schema from "./schema";

// One pool per server process. `prepare: false` keeps it compatible with pgbouncer-style poolers.
const client = postgres(env.DATABASE_URL, { max: 10, prepare: false });

export const db = drizzle(client, { schema });
