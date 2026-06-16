/**
 * Validated runtime environment for the Next BFF — server-only usage (docs/PHASE2.md §5).
 *
 * One home for env access: db/client, redis, actions, and route handlers read from here, never
 * `process.env` directly. Throws a readable error at startup if something required is missing.
 */
import { z } from "zod";

const schema = z.object({
  // Postgres (the durable system of record). Defaults to docker-compose in .env.example.
  DATABASE_URL: z.string().min(1, "DATABASE_URL is required — see .env.example"),
  // Redis (queue + live trace stream + cancel flag).
  REDIS_URL: z.string().min(1, "REDIS_URL is required — see .env.example"),
  // Absolute path to workspaces/ for the source viewer + topology/scenarios reads.
  // Optional: lib/workspace.ts falls back to the in-repo workspaces dir.
  WORKSPACES_ROOT: z.string().optional(),
  WORKSPACE_DEFAULT: z.string().default("acme-checkout"),
});

function load() {
  const parsed = schema.safeParse(process.env);
  if (!parsed.success) {
    const issues = parsed.error.issues.map((i) => `  - ${i.path.join(".")}: ${i.message}`).join("\n");
    throw new Error(`Invalid environment:\n${issues}`);
  }
  return parsed.data;
}

export const env = load();
