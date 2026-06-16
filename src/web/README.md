# Biggy — Web

The Phase 2 web app: a thin **trigger + viewer** over the same investigation engine the CLI runs. It
does **not** re-implement any reasoning — it enqueues a job, a Python worker runs the engine, and the
browser streams the live trace and renders the grounded briefing. Architecture + plan:
[`../../docs/PHASE2.md`](../../docs/PHASE2.md).

## Architecture (motion vs memory)

```
Browser (React / shadcn)
  │ Server Actions (enqueue) · EventSource (SSE, live trace) · RSC reads
  ▼
Next.js server  ── the API / BFF (no FastAPI) ───────────────────────────
  │ XADD biggy:jobs        │ Drizzle reads        │ SSE relay (XREAD)
  ▼                        ▼                      ▲
Redis (motion)          Postgres (memory)      Worker (Python) — imports `biggy`,
queue · trace stream    jobs · audit · history  runs investigate(), writes PG + streams Redis
```

- **Redis** carries the run while it happens (job queue · live trace stream · cancel flag).
- **Postgres** is the durable record (jobs + lifecycle, tool-call audit, trace, citations, history).
- **Next is the API** — it talks to Redis + Postgres directly; the only Python process is the worker.

## Tech stack

Next.js 16 (App Router, Turbopack) · React 19 · Tailwind v4 · shadcn/ui (`base-nova`, Base UI) ·
Drizzle ORM (postgres-js) · ioredis · zod · TypeScript · pnpm.

## Run (needs the full stack)

From the repo root (Redis + Postgres + the worker must be up):

```bash
docker compose up -d                  # Redis + Postgres
pnpm -C src/web install
pnpm -C src/web db:push               # apply the Drizzle schema
python -m biggy.worker                # consume jobs (set BIGGY_FAKE_RUN=1 for a keyless demo)
pnpm -C src/web dev                   # http://localhost:3000/investigations
```

`.env.local` here holds `DATABASE_URL` + `REDIS_URL` (defaults match `docker-compose.yml`).

## Scripts

| Command | Description |
|---|---|
| `pnpm dev` | Dev server (Turbopack) |
| `pnpm build` | Production build (standalone output) |
| `pnpm start` | Serve the production build |
| `pnpm lint` · `pnpm typecheck` | ESLint · `tsc --noEmit` |
| `pnpm db:push` / `db:generate` | Apply / generate Drizzle migrations |

## Structure

```
src/web/
├─ app/
│  ├─ investigations/page.tsx          # list + composer (RSC)
│  ├─ investigations/[id]/page.tsx     # detail shell → <LiveRun/>
│  └─ api/{investigations/[id]/events, source, topology, healthz}/route.ts
├─ components/investigations/          # composer, briefing, hypothesis-card, citation, live-run,
│                                      # trace-panel, source-viewer, blast-radius, …
├─ components/ui/                      # shadcn/ui primitives
├─ lib/                                # contracts (zod) · db (Drizzle) · redis · workspace · actions · format
└─ hooks/use-event-stream.ts           # SSE subscription
```

## Contracts (DRY)

[`lib/contracts.ts`](lib/contracts.ts) (zod) mirrors the Python sources of truth —
`biggy/engine/schemas.py` (briefing shape) and `biggy/engine/trace.py` (trace-event union). A
cross-language parity test (`src/cli/tests/test_contract_parity.py`) fails if they drift.

> **shadcn note:** this is the `base-nova` style (Base UI), not Radix — polymorphism uses the
> **`render` prop**, not `asChild`.

## Deploy

`output: "standalone"` + [`Dockerfile`](Dockerfile) (build from the repo root). Provide
`DATABASE_URL`, `REDIS_URL`, and `WORKSPACES_ROOT` at runtime; the worker deploys from
[`../cli/Dockerfile`](../cli/Dockerfile).
