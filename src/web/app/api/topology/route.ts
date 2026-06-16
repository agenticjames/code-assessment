import { NextResponse } from "next/server";

import { env } from "@/lib/env";
import { readTopology } from "@/lib/workspace";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const workspace = url.searchParams.get("workspace") || env.WORKSPACE_DEFAULT;
  const topo = await readTopology(workspace);
  if (!topo) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json(topo);
}
