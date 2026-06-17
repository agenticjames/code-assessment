/**
 * Read-only vault access for the web (docs/PHASE2.md §3 #7). Mirrors the engine's access boundary:
 * only `telemetry/` + standing docs are readable; `scenarios/`, `HIDDEN_TRUTH`, and `..` are denied.
 * Server-only.
 */
import "server-only";

import { promises as fs } from "node:fs";
import path from "node:path";

import { parse as parseYaml } from "yaml";

import { env } from "@/lib/env";
import { manifestSchema, type Manifest } from "@/lib/manifest";

function workspacesRoot(): string {
  // Env override, else the in-repo workspaces/ (../../workspaces relative to the web project).
  return env.WORKSPACES_ROOT ?? path.resolve(process.cwd(), "../../workspaces");
}

const DENY = ["scenarios/", "hidden_truth"];

export function isAllowed(relPath: string): boolean {
  const p = relPath.replace(/\\/g, "/").replace(/^\.?\//, "").toLowerCase();
  if (!p || p.includes("..")) return false;
  return !DENY.some((d) => p.includes(d));
}

export type SourceFile = { path: string; lines: string[] };

/** Resolve a citation path (with an optional `:line` suffix already stripped) to its file lines. */
export async function readSource(workspace: string, relPath: string): Promise<SourceFile | null> {
  const clean = relPath
    .replace(/\\/g, "/")
    .replace(/^\.?\//, "")
    .replace(/:\d+$/, "");
  if (!isAllowed(clean)) return null;

  const wsDir = path.resolve(workspacesRoot(), workspace);
  const full = path.resolve(wsDir, clean);
  // Defense in depth: the resolved path must stay inside the workspace dir.
  if (full !== wsDir && !full.startsWith(wsDir + path.sep)) return null;

  try {
    const text = await fs.readFile(full, "utf8");
    return { path: clean, lines: text.split("\n") };
  } catch {
    return null;
  }
}

export type Topology = Record<
  string,
  {
    tier?: string;
    depends_on?: string[];
    shared_by?: string[];
    type?: string;
    external?: boolean;
    owner?: string;
  }
>;

/** Parse topology/services.yaml (the lightweight dependency graph) for the blast-radius viz. */
export async function readTopology(workspace: string): Promise<Topology | null> {
  const src = await readSource(workspace, "topology/services.yaml");
  if (!src) return null;
  try {
    return (parseYaml(src.lines.join("\n")) ?? null) as Topology | null;
  } catch {
    return null;
  }
}

/**
 * The committed workspace manifest (scenario presets + corpus profile). The engine generates it
 * (`biggy workspace manifest`); the web reads it because it cannot read the denied `scenarios/`
 * dir and must not re-parse telemetry. Validated with zod — a stale/corrupt file returns null.
 */
export async function readManifest(workspace: string): Promise<Manifest | null> {
  const src = await readSource(workspace, "manifest.json");
  if (!src) return null;
  try {
    return manifestSchema.parse(JSON.parse(src.lines.join("\n")));
  } catch {
    return null;
  }
}
