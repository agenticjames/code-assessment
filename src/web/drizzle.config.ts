import { defineConfig } from "drizzle-kit";

// DATABASE_URL falls back to the docker-compose Postgres so `pnpm db:push` works out of the box.
export default defineConfig({
  schema: "./lib/db/schema.ts",
  out: "./drizzle",
  dialect: "postgresql",
  dbCredentials: {
    url: process.env.DATABASE_URL ?? "postgres://biggy:biggy@localhost:5433/biggy",
  },
});
