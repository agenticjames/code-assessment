import { NextResponse } from "next/server";

import { env } from "@/lib/env";
import { readSource } from "@/lib/workspace";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const workspace = url.searchParams.get("workspace") || env.WORKSPACE_DEFAULT;
  const pathParam = url.searchParams.get("path") ?? "";
  const line = Number(url.searchParams.get("line")) || null;

  const src = await readSource(workspace, pathParam);
  if (!src) return NextResponse.json({ error: "not found or not allowed" }, { status: 404 });
  return NextResponse.json({ ...src, line });
}
