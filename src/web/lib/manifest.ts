/**
 * The TypeScript shape of `workspaces/<ws>/manifest.json` — the agent-safe artifact the engine
 * generates (`biggy workspace manifest`). The web reads it instead of the denied `scenarios/` dir,
 * and instead of re-implementing the engine's telemetry parsing. This is the single source for the
 * composer's scenario presets and the timeline's corpus profile.
 *
 * Mirrors `biggy/engine/workspace/manifest.py`. Validated with zod on read so a stale/corrupt file
 * fails loudly rather than rendering garbage.
 */
import { z } from "zod";

export const scenarioSeedSchema = z.object({
  id: z.string(),
  label: z.string(),
  query: z.string(),
  mode: z.enum(["live", "retrospective"]),
  as_of: z.string().nullish(), // live
  look_back: z.string().nullish(), // live
  range: z.object({ from: z.string(), to: z.string() }).nullish(), // retrospective
});
export type ScenarioSeed = z.infer<typeof scenarioSeedSchema>;

export const corpusProfileSchema = z.object({
  min: z.string().nullable(),
  max: z.string().nullable(),
  buckets: z.number(),
  density: z.array(z.number()),
});
export type CorpusProfile = z.infer<typeof corpusProfileSchema>;

export const manifestSchema = z.object({
  workspace: z.string(),
  scenarios: z.array(scenarioSeedSchema),
  corpus: corpusProfileSchema,
});
export type Manifest = z.infer<typeof manifestSchema>;
