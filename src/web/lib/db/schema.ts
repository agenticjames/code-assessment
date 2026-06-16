/**
 * Drizzle schema — the SINGLE source of truth for the Postgres durable store (docs/PHASE2.md §4.3).
 *
 * Drizzle owns the schema + migrations; the Python worker (biggy/worker/db.py) only writes rows to
 * these exact tables/columns. Keep the two in sync by column name.
 */
import {
  boolean,
  index,
  integer,
  jsonb,
  pgTable,
  real,
  text,
  timestamp,
  uniqueIndex,
  uuid,
} from "drizzle-orm/pg-core";

/** One investigation (the job + its denormalized summary + the full artifacts). */
export const investigations = pgTable(
  "investigations",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
    // queued | running | succeeded | failed | canceled
    status: text("status").notNull().default("queued"),
    workspace: text("workspace").notNull(),
    scenario: text("scenario"),
    query: text("query").notNull(),
    provider: text("provider").notNull(),
    model: text("model").notNull(),
    maxSteps: integer("max_steps").notNull(),
    asOf: timestamp("as_of", { withTimezone: true }),
    windowStart: timestamp("window_start", { withTimezone: true }),
    windowEnd: timestamp("window_end", { withTimezone: true }),
    startedAt: timestamp("started_at", { withTimezone: true }),
    finishedAt: timestamp("finished_at", { withTimezone: true }),
    durationMs: integer("duration_ms"),
    stepCount: integer("step_count"),
    // denormalized from result_json so the history list renders without parsing the artifact
    outcome: text("outcome"),
    summary: text("summary"),
    topService: text("top_service"),
    topConfidence: real("top_confidence"),
    groundingVerified: integer("grounding_verified"),
    groundingTotal: integer("grounding_total"),
    recommendedAction: text("recommended_action"),
    error: text("error"),
    resultJson: jsonb("result_json"),
    ledgerJson: jsonb("ledger_json"),
  },
  (t) => [index("investigations_status_created_idx").on(t.status, t.createdAt)],
);

/** The per-step tool-call audit — "what was called" (maps 1:1 to ledger.tool_calls). */
export const toolCalls = pgTable(
  "tool_calls",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    investigationId: uuid("investigation_id")
      .notNull()
      .references(() => investigations.id, { onDelete: "cascade" }),
    step: integer("step").notNull(),
    name: text("name").notNull(),
    args: jsonb("args").notNull(),
    resultPreview: text("result_preview").notNull().default(""),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [index("tool_calls_investigation_step_idx").on(t.investigationId, t.step)],
);

/** The durable trace — drives SSE replay (total order by seq). */
export const traceEvents = pgTable(
  "trace_events",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    investigationId: uuid("investigation_id")
      .notNull()
      .references(() => investigations.id, { onDelete: "cascade" }),
    seq: integer("seq").notNull(),
    ts: timestamp("ts", { withTimezone: true }).notNull(),
    type: text("type").notNull(),
    payload: jsonb("payload").notNull(),
  },
  (t) => [uniqueIndex("trace_events_investigation_seq_idx").on(t.investigationId, t.seq)],
);

/** Citations projected from the verdict's evidence — clickable links + queryable grounding. */
export const citations = pgTable(
  "citations",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    investigationId: uuid("investigation_id")
      .notNull()
      .references(() => investigations.id, { onDelete: "cascade" }),
    hypothesisId: text("hypothesis_id").notNull(),
    stance: text("stance").notNull(), // support | refute
    claim: text("claim").notNull(),
    snippet: text("snippet").notNull(),
    sourcePath: text("source_path").notNull(),
    sourceLine: integer("source_line"),
    verified: boolean("verified"),
  },
  (t) => [index("citations_investigation_idx").on(t.investigationId)],
);

export type InvestigationRow = typeof investigations.$inferSelect;
export type NewInvestigationRow = typeof investigations.$inferInsert;
export type ToolCallRow = typeof toolCalls.$inferSelect;
export type TraceEventRow = typeof traceEvents.$inferSelect;
export type CitationRow = typeof citations.$inferSelect;
