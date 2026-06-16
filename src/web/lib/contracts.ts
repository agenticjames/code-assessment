/**
 * Cross-language wire contracts (docs/PHASE2.md §3 #4, §4).
 *
 * The TypeScript mirror of the Python sources of truth:
 *   - the briefing shape  ← biggy/engine/schemas.py (InvestigationResult, Hypothesis, EvidenceRef)
 *   - the trace-event union ← biggy/engine/trace.py EVENT_* (+ worker lifecycle events)
 *   - the job payload     ↔ biggy/worker/contracts.py Job
 *
 * Keep tiny. A parity test (src/cli/tests/test_contract_parity.py) fails if the event union here
 * drifts from the Python source, so adding an event forces touching both sides.
 */
import { z } from "zod";

// ---------- 1. Job payload (Next `XADD biggy:jobs` → worker). Mirrors worker/contracts.py Job. ----------
export const jobSchema = z.object({
  id: z.uuid(),
  query: z.string().min(1),
  workspace: z.string().min(1),
  scenario: z.string().nullable(),
  provider: z.string().min(1),
  model: z.string().min(1),
  max_steps: z.number().int().positive(),
});
export type Job = z.infer<typeof jobSchema>;

// ---------- 2. Briefing shape. Mirrors biggy/engine/schemas.py. Render defensively. ----------
export const evidenceRefSchema = z.object({
  claim: z.string(),
  snippet: z.string(),
  source: z.string(), // "<path>:<line>"
  verified: z.boolean().nullish(), // set by the deterministic verify phase
});
export type EvidenceRef = z.infer<typeof evidenceRefSchema>;

export const hypothesisStatusSchema = z.enum(["open", "confirmed", "ruled_out"]);
export type HypothesisStatus = z.infer<typeof hypothesisStatusSchema>;

export const hypothesisSchema = z.object({
  id: z.string(),
  statement: z.string(),
  service: z.string().nullish(),
  confidence: z.number(),
  status: hypothesisStatusSchema,
  disconfirming_test: z.string().default(""),
  ruled_out_reason: z.string().nullish(),
  supporting: z.array(evidenceRefSchema).default([]),
  contradicting: z.array(evidenceRefSchema).default([]),
});
export type Hypothesis = z.infer<typeof hypothesisSchema>;

export const outcomeSchema = z.enum(["root_cause", "inconclusive"]);
export type Outcome = z.infer<typeof outcomeSchema>;

// A signal the agent considered then dismissed as noise (mirrors schemas.py NoiseItem).
export const noiseItemSchema = z.object({
  item: z.string(),
  reason: z.string(),
});
export type NoiseItem = z.infer<typeof noiseItemSchema>;

export const investigationResultSchema = z.object({
  query: z.string(),
  outcome: outcomeSchema,
  summary: z.string(),
  recommended_action: z.string().nullish(),
  // Paste-ready responder update; nullish so older runs (no field) still parse.
  stakeholder_note: z.string().nullish(),
  open_questions: z.array(z.string()).default([]),
  noise_dropped: z.array(noiseItemSchema).default([]),
  hypotheses: z.array(hypothesisSchema).default([]),
});
export type InvestigationResult = z.infer<typeof investigationResultSchema>;

export const groundingSchema = z.object({
  claims_total: z.number(),
  claims_verified: z.number(),
  ungrounded: z.array(z.string()).default([]),
});
export type Grounding = z.infer<typeof groundingSchema>;

// ---------- 3. Trace event union. type names MUST match engine/trace.py EVENT_* + worker lifecycle.
//             Enforced by src/cli/tests/test_contract_parity.py. ----------
export const TRACE_EVENT_TYPES = [
  "status",
  "scenario",
  "phase",
  "hypotheses",
  "tool_call",
  "tool_result",
  "thinking_done",
  "budget_exhausted",
  "grounding",
  "verdict",
  "error",
  "canceled",
  "done",
] as const;
export type TraceEventType = (typeof TRACE_EVENT_TYPES)[number];

/** Envelope helper: every event is `{ seq, ts, type, data }`, ordered by `seq`. */
const ev = <T extends string, D extends z.ZodTypeAny>(type: T, data: D) =>
  z.object({ seq: z.number().int(), ts: z.string(), type: z.literal(type), data });

const traceHypothesisSchema = z.object({
  id: z.string(),
  statement: z.string(),
  service: z.string().nullish(),
  confidence: z.number(),
});

export const traceEventSchema = z.discriminatedUnion("type", [
  ev("status", z.object({ state: z.literal("running") })),
  ev(
    "scenario",
    z.object({
      query: z.string(),
      as_of: z.string(),
      window: z.tuple([z.string(), z.string()]),
      files: z.number(),
    }),
  ),
  ev("phase", z.object({ name: z.string() })),
  ev("hypotheses", z.object({ hypotheses: z.array(traceHypothesisSchema) })),
  ev("tool_call", z.object({ step: z.number(), name: z.string(), args: z.record(z.string(), z.unknown()) })),
  ev(
    "tool_result",
    z.object({ step: z.number(), name: z.string(), preview: z.string(), source: z.string().nullish() }),
  ),
  ev("thinking_done", z.object({ step: z.number() })),
  ev("budget_exhausted", z.object({ max_steps: z.number() })),
  ev("grounding", z.object({ verified: z.number(), total: z.number() })),
  ev("verdict", investigationResultSchema),
  ev("error", z.object({ message: z.string() })),
  ev("canceled", z.object({})),
  ev("done", z.object({ status: z.enum(["succeeded", "failed", "canceled"]) })),
]);
export type TraceEvent = z.infer<typeof traceEventSchema>;
