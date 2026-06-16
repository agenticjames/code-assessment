# Phase 2 — Web App Integration (the living build plan)

> Companion to [`DESIGN.md`](DESIGN.md) (*what/why*), [`ARCHITECTURE.md`](ARCHITECTURE.md)
> (*how the engine is built*), and [`DELIVERY.md`](DELIVERY.md) (*the increment sequence*).
> **This doc is the source of truth for Phase 2** — the web app that wraps the same engine the
> CLI drives. It is a *living* document: implementation is checked against it, and the
> **Progress log** (§11) is updated as phases land. Keep referring back to it.

**Status:** shipped — all phases P0–P8 landed and were browser-verified (see the Progress log, §11).
**Maps to** `DELIVERY.md` Inc 6–8, with the durable store moved from Redis to Postgres (§2).

---

## 0. Thesis

The CLI is a thin shell over an **importable, surface-agnostic engine**
(`orchestrator.investigate(config, tracer) -> (InvestigationResult, Ledger)`). Phase 2 does **not**
shell out to the `biggy` binary — it imports the same package from a **worker process**, and the
existing **Next.js app is the API/BFF**. There is **no FastAPI tier**: Next talks to Redis +
Postgres directly; the only Python process is the worker.

> **Motion vs memory.** **Redis** carries the run while it happens (job queue · live trace stream ·
> cancel flag · vector index). **Postgres** remembers it forever (jobs + lifecycle, the per-step
> tool-call audit, the durable trace, citations + grounding, history). *Redis where it's hot,
> Postgres where it's true.*

### Why no FastAPI (the deliberate non-choice)
The only thing that forced a Python web tier was the queue: RQ/Celery serialize a *Python callable*
onto Redis, so only Python could enqueue. We use a **language-neutral JSON job on a Redis Stream**
instead — Next `XADD`s, the worker `XREADGROUP`s — so Node enqueues directly and the Python HTTP
server disappears. Accepted cost: **a shared contract maintained in two languages** (§3/§4) and a
little vault-read logic mirrored in TS (`/api/source`). We would add a thin Python read service back
only for *synchronous* engine calls from the web, or to serve the engine API to non-Next clients.

---

## 1. Architecture

```
Browser (React / shadcn)
   │  fetch + Server Actions (mutations) · EventSource (SSE, live trace)
   ▼
Next.js server  ── the API / BFF ────────────────────────────────────────────
   │  RSC reads (Drizzle)        │ enqueue (XADD)          │ SSE relay (XREAD)
   ▼                             ▼                         ▲
Postgres  ◄── lifecycle+artifacts ── Worker (only Python) ─┘ publishes trace
 (memory)                            imports `biggy`; XREADGROUP biggy:jobs;
   ▲                                 runs investigate(cfg, Tracer(RedisPgSink)); writes PG
   └──────────────── Redis (motion) ◄────────────────────────┘
                     biggy:jobs · trace:{id} · cancel:{id} · idx:incidents (reserved)
```

**Lifecycle of one run:**
1. **Create** — Server Action validates, `INSERT investigations(status=queued)` (PG) → `XADD biggy:jobs` (Redis) → redirect to `/investigations/{id}`.
2. **Claim** — worker `XREADGROUP` pops the job; `status=running`, `started_at`.
3. **Run** — `investigate(cfg, Tracer(RedisPgSink))`; each step emits a trace event → `XADD trace:{id}` (live) **and** `INSERT trace_events` (durable). Cancel checked between steps via `cancel:{id}`.
4. **Finish** — worker writes verdict + ledger to `investigations`, batch-inserts `tool_calls` + `citations`, denormalizes summary columns, emits `done`. (`failed`/`canceled` emit `error`/`canceled` then `done`.)
5. **Watch** — browser opens SSE `…/events`; the handler tails `trace:{id}` while live (resumes by stream id), or replays `trace_events` from PG once the stream has expired. A terminal event closes the stream.
6. **Read** — list + detail first paint are RSC reads straight from Postgres.

---

## 2. What this revises in the locked docs
`DELIVERY` Inc 6 / `ARCHITECTURE §5` said *"Redis job + **result store**"*. Phase 2 **moves the
durable store to Postgres** and keeps Redis for queue + live stream + vectors. ADR to add to
`ARCHITECTURE §7`: *"Postgres is the system of record; Redis is ephemeral motion. Splitting them
keeps history/audit queryable and durable; Redis is the wrong home for an audit trail."*

---

## 3. DRY — the seven single sources of truth

Every fact has exactly one home; every other surface derives from it. This table is the contract for
"don't repeat yourself" — if you find yourself defining one of these twice, stop.

| # | Source of truth | Owns | Derived / mirrored by |
|---|---|---|---|
| 1 | `engine/schemas.py` (Pydantic) | the briefing shape (`InvestigationResult`, `Hypothesis`, `EvidenceRef`, `Grounding`) | `result_json` (PG) · `lib/contracts.ts` (zod mirror) · briefing components · `cli/render.py` |
| 2 | `engine/trace.py` `EVENT_*` + `Tracer` | the live event vocabulary | `RedisPgSink` · `lib/contracts.ts` union · `use-event-stream` · `trace-event-item` |
| 3 | `lib/db/schema.ts` (Drizzle) | the durable Postgres schema | generated migrations · worker `psycopg` writes · RSC reads |
| 4 | `lib/contracts.ts` (zod) | the cross-language wire contract (job + events + briefing) | `worker/contracts.py` (Pydantic mirror) · action validation · `XADD` payload |
| 5 | `app/globals.css` tokens | all UI color (light+dark, brand) | every component via Tailwind classes — **never hardcode hex** |
| 6 | `components/ui/*` (shadcn) | UI primitives | every feature component composes them (add to the registry, don't hand-roll) |
| 7 | engine vault access-boundary | which paths are readable | `/api/source` guard mirrors it (telemetry/ + standing docs; deny `scenarios/`, `HIDDEN_TRUTH`, `..`) |

**Drift control:** contracts (#4) stay tiny; a unit test asserts the TS trace-event type set equals
`trace.py`'s `EVENT_*` set. Presentational logic is mirrored, not duplicated: the React briefing
tree is structurally 1:1 with `cli/render.py` (§6).

---

## 4. Contracts (canonical — both languages must agree)

### 4.1 Job payload (Next `XADD biggy:jobs` → worker)
```jsonc
{ "id": "<uuid>", "query": "string", "workspace": "acme-checkout",
  "scenario": "A" | null, "provider": "google_genai",
  "model": "gemini-3.1-flash-lite", "max_steps": 12 }
```
TS: `src/web/lib/contracts.ts` (zod `jobSchema`). Python: `biggy/worker/contracts.py` (Pydantic `Job`).

### 4.2 Trace event (worker → Redis stream + `trace_events` → SSE)
Envelope `{ seq:int, ts:isostring, type:string, data:object }`. Total order by `seq` (assigned by the
sink). The engine-emitted half is defined in `trace.py`; the worker adds lifecycle events.

| `type` | `data` | emitted by |
|---|---|---|
| `status` | `{ state: "running" }` | worker |
| `scenario` | `{ query, as_of, window:[s,e], files:int }` | engine |
| `phase` | `{ name }` (hypothesize/investigate/adjudicate/verify) | engine |
| `hypotheses` | `{ hypotheses:[{ id, statement, service?, confidence }] }` | engine |
| `tool_call` | `{ step, name, args }` | engine |
| `tool_result` | `{ step, name, preview, source? }` | engine |
| `thinking_done` | `{ step }` | engine |
| `budget_exhausted` | `{ max_steps }` | engine |
| `grounding` | `{ verified, total }` | engine (verify phase) |
| `verdict` | `InvestigationResult` (§4.4) | engine |
| `error` | `{ message }` | worker |
| `canceled` | `{}` | worker |
| `done` | `{ status: "succeeded"\|"failed"\|"canceled" }` | worker (terminal) |

### 4.3 Postgres schema (owned by Drizzle in `src/web/lib/db/schema.ts`; worker writes via psycopg)
```
investigations
  id uuid PK · created_at · updated_at · status text
  workspace · scenario? · query · provider · model · max_steps int
  as_of? · window_start? · window_end?
  started_at? · finished_at? · duration_ms? · step_count?
  outcome? · summary? · top_service? · top_confidence real?
  grounding_verified? · grounding_total? · recommended_action? · error?
  result_json jsonb? · ledger_json jsonb?
tool_calls    id PK · investigation_id FK→ · step · name · args jsonb · result_preview · created_at
trace_events  id PK · investigation_id FK→ · seq · ts · type · payload jsonb · UNIQUE(investigation_id, seq)
citations     id PK · investigation_id FK→ · hypothesis_id · stance(support|refute) · claim · snippet
              · source_path · source_line? · verified?
indexes: investigations(status, created_at desc) · tool_calls(investigation_id, step)
         · trace_events(investigation_id, seq) · citations(investigation_id)
FKs ON DELETE CASCADE. Migrations owned by Drizzle; worker only reads/writes rows.
```

### 4.4 Briefing shape (`result_json`, from `biggy.engine.schemas.InvestigationResult`)
```
InvestigationResult = { query, outcome: "root_cause"|"inconclusive", summary,
  recommended_action?, open_questions: string[],
  hypotheses: Hypothesis[] }            // render ranked by confidence desc
Hypothesis = { id, statement, service?, confidence, status: "open"|"confirmed"|"ruled_out",
  disconfirming_test, ruled_out_reason?, supporting: EvidenceRef[], contradicting: EvidenceRef[] }
EvidenceRef = { claim, snippet, source: "<path>:<line>", verified?: bool }
Grounding (on the ledger) = { claims_total, claims_verified, ungrounded: string[] }
```
The grounding badge = `claims_verified / claims_total` (worker denormalizes to columns). Render
**defensively** — treat every field except the shape itself as possibly absent.

### 4.5 Redis keys
| key | type | role |
|---|---|---|
| `biggy:jobs` | stream + consumer group `workers` | work queue |
| `trace:{id}` | stream (TTL 24h, MAXLEN ~1000) | live trace fan-out |
| `cancel:{id}` | string (TTL 1h) | cancel flag, checked between steps |
| `idx:incidents` | vector | semantic memory — **reserved** for engine Inc 5; not built here |

### 4.6 HTTP surface (Next)
Mutations = **Server Actions**; client reads/streams = **Route Handlers**; first paint = **RSC**.
| kind | path / action | does |
|---|---|---|
| action | `createInvestigation(form)` | validate · insert (PG) · `XADD` (Redis) · redirect |
| action | `cancelInvestigation(id)` | `SET cancel:{id}` |
| RSC | `/investigations`, `/investigations/[id]` | Drizzle reads for first paint |
| GET | `/api/investigations/[id]/events` | **SSE** — tail Redis live / replay PG when expired |
| GET | `/api/investigations/[id]` | JSON detail (client refresh / poll fallback) |
| GET | `/api/topology?workspace=` | topology graph (blast-radius) |
| GET | `/api/scenarios?workspace=` | picker data (id, slug, query, severity) — never HIDDEN_TRUTH |
| GET | `/api/source?workspace=&path=&line=` | file slice for source viewer; **access-bounded** |

---

## 5. File structure — backend (worker + Next BFF)

Two deployables, one engine. Each module has one responsibility; the contract modules are the only
cross-language duplication, kept deliberately tiny.

```
src/cli/biggy/
  engine/trace.py            DONE (sink seam) · schemas/grounding/phases/context: reuse as-is
  engine/phases/investigate.py   +tracer.tool_result(...) · +cancel check     (seam gaps 1 & 3)
  engine/phases/adjudicate.py    +tracer.verdict(result)                       (seam gap 2)
  engine/context.py              +should_cancel hook (callable injected by worker; CLI = no-op)
  worker/                    NEW — the only Python service (python -m biggy.worker)
    __main__.py    boot: load env, connect redis+pg, run the consume loop
    contracts.py   Pydantic Job (mirrors lib/contracts.ts jobSchema) — the one shared shape
    redis_io.py    XREADGROUP claim · XACK · XADD trace:{id} (MAXLEN/TTL) · cancel:{id} · ensure group
    db.py          psycopg writer: create/claim/finish/fail/cancel · batch tool_calls + citations
    sink.py        RedisPgSink(TraceSink): one emit() → XADD (live) + INSERT trace_events (durable)
    runner.py      one job's lifecycle; takes an INJECTABLE `investigate` (real | fake for tests)
    fake.py        FakeRun — replays the committed sample ledger as timed events (keyless demo/e2e)

src/web/
  lib/
    env.ts         parsed/validated env (DATABASE_URL, REDIS_URL, WORKSPACES_ROOT, WORKSPACE_DEFAULT)
    contracts.ts   zod: jobSchema · traceEvent union · briefing types          ← SSOT mirror
    db/schema.ts   Drizzle table defs (owns the schema) · client.ts (pooled, server-only) · queries.ts
    redis.ts       ioredis singleton (server-only)
    workspace.ts   vault read + access-boundary guard (mirrors engine)
    format.ts      shared formatters: confidencePct · duration · relativeTime · outcomeLabel
    actions.ts     server actions: createInvestigation · cancelInvestigation
  app/
    layout.tsx           REUSE the existing shell (sidebar+header); repoint nav → Investigations
    investigations/page.tsx        RSC: list + composer
    investigations/[id]/page.tsx   RSC shell: getInvestigation()+getToolCalls() → <LiveRun initial/>
    api/investigations/[id]/events/route.ts   SSE (replay PG → tail Redis)
    api/investigations/[id]/route.ts          JSON detail (poll fallback)
    api/{topology,scenarios,source}/route.ts  bounded vault reads
  drizzle/             generated migrations (drizzle-kit)
```

**Why:** reads for first paint are RSC straight from Postgres (no client DB, no waterfall);
mutations are Server Actions (`createInvestigation` = zod-validate → INSERT → XADD → redirect); only
genuinely live/interactive things are Route Handlers (SSE) + client components. `lib/` holds every
non-React capability so each capability has exactly one home and components stay thin.

---

## 6. UI component architecture

**Boundary doctrine (RSC-first).** Pages are Server Components that fetch from PG and pass plain data
down. Pure presentational components (`briefing`, `hypothesis-card`, `evidence-list`, `status-badge`,
`confidence-bar`, `grounding-badge`) are **client-agnostic** — no `"use client"`, no server-only
imports — so the *same* component renders in the RSC first paint of a finished run **and** re-renders
inside the live client as events arrive. Only interactivity / the event stream is client.

**Component tree** (`components/investigations/`; shared atoms defined once, reused everywhere):
```
LIST                                      DETAIL
  composer/composer.tsx ....... client      live-run.tsx ......... client: SSE + reducer + run state
  composer/scenario-picker.tsx              ├─ run-header.tsx ........ status-badge + grounding-badge + meta
  composer/advanced-options.tsx             ├─ run-tabs.tsx .......... shadcn Tabs
  investigations-table.tsx .... rows        ├─ trace-panel.tsx ....... client: scroll-area of events
                                            │    └─ trace-event-item.tsx .. switch on event.type (the union)
SHARED ATOMS (one definition)               ├─ briefing.tsx .......... mirrors render.py _briefing
  status-badge.tsx ... status→token         │    ├─ hypothesis-card.tsx ... mirrors _hypothesis_panel
  confidence-bar.tsx . 0–1 bar (built)      │    ├─ evidence-list.tsx ..... mirrors _evidence
  grounding-badge.tsx  ✓ n/n (Badge)        │    │    └─ citation.tsx ...... client: opens source-viewer
  citation.tsx ....... path:line chip       │    ├─ open-questions.tsx
  outcome-label.tsx .. root/inconclusive    │    ├─ recommended-action.tsx
  relative-time.tsx .. "2m ago"             │    └─ stakeholder-note.tsx ... client: copy → sonner
                                            ├─ tool-call-audit.tsx ... table from tool_calls (PG)
hooks/use-event-stream.ts                   ├─ source-viewer.tsx ..... client: Sheet + /api/source
  EventSource + reconnect + Last-Event-ID   └─ blast-radius.tsx ...... client: SVG from /api/topology
```

**DRY across surfaces — the briefing renders one schema in two languages.** Keep the React tree 1:1
with `cli/render.py` so behavior can't drift:

| `cli/render.py` | React component | shared rule |
|---|---|---|
| `_briefing` | `briefing.tsx` | rank hypotheses by confidence desc; show outcome |
| `_hypothesis_panel` | `hypothesis-card.tsx` | status color confirmed/ruled_out/open; show `ruled_out_reason` |
| `_evidence` | `evidence-list.tsx` | `verified` → tick / `UNVERIFIED` flag |
| `_grounding_panel` | `grounding-badge.tsx` | green iff `verified === total` |
| `_conf_bar` | `confidence-bar.tsx` | one bar everywhere |

**shadcn — reuse / add / build:**
- **Reuse (13 present):** button, input, card, badge, table, sheet, skeleton, tooltip, separator, breadcrumb, dropdown-menu, avatar, sidebar.
- **Add from registry:** `select`, `textarea`, `tabs`, `scroll-area`, `sonner`, `collapsible`.
- **Hand-build (no primitive; all token-colored):** `confidence-bar`, `citation`, `trace-event-item`, `blast-radius`.

---

## 7. Phases (each ends demoable; tracked as tasks; check off in §11)

Vertical slices — a thin end-to-end thread lands at P4, then enriches. The static briefing UI
parallelizes from P2 against the committed sample ledger ([`docs/sample-run/ledger.json`](sample-run/ledger.json)).

- **P0 — Foundations & contracts.** docker-compose (have it); `.env.example`; `lib/env.ts`;
  `lib/contracts.ts` ↔ `worker/contracts.py` + a parity test vs `trace.py` `EVENT_*`; web deps
  (drizzle-orm, postgres, ioredis, zod, drizzle-kit) + worker extra (redis, psycopg); add the 6
  shadcn primitives; add `--success/--warning/--info` tokens to `globals.css`.
  **Done:** `docker compose up` healthy; both contract modules type-check; primitives + tokens present.
- **P1 — Close the engine seam.** Emit `tool_result` (investigate), `verdict` (adjudicate); add a
  `should_cancel` hook checked between steps. CLI output byte-unchanged.
  **Done:** a capturing-sink test asserts the full event sequence; ruff + pytest green.
- **P2 — Persistence.** Drizzle `schema.ts` + generated migration; `worker/db.py` writer;
  `lib/db/queries.ts` reads. *(Parallel: build static briefing components vs the sample ledger.)*
  **Done:** migration applies to compose Postgres; a worker-db round-trip test passes.
- **P3 — Worker.** `redis_io` (consumer group), `sink` (RedisPgSink), `runner` (lifecycle, injectable
  investigate), `fake.py`, `__main__`. Failure/cancel handled; idempotent claim.
  **Done:** offline fake-run drives PG rows + stream events + terminal `done`; `python -m biggy.worker` boots on compose.
- **P4 — Walking skeleton (e2e, poll).** `actions.createInvestigation` (INSERT+XADD); list page
  (composer + table); detail RSC renders the finished briefing by poll (no SSE yet).
  **Done (Inc 6):** browser trigger → worker (fake) runs → briefing renders.
- **P5 — Live trace (SSE).** SSE route (replay+tail); `use-event-stream`; `live-run` reducer;
  `trace-panel` + `trace-event-item`; `run-tabs`; confidence bars animate.
  **Done (Inc 7):** trigger → watch it reason live → briefing resolves; reload mid-run replays.
- **P6 — Tangible grounding.** `/api/source` (bounded); `source-viewer` Sheet + `useSourceViewer`;
  wire `citation` chips; `tool-call-audit` tab.
  **Done (Inc 7):** clicking a verified citation opens the source at the line; audit lists every tool call.
- **P7 — Graph & states.** `/api/topology`; `blast-radius` SVG (chain lit, herring greyed); history
  filters; empty/loading/error/canceled states; reduced-motion; sonner toasts.
  **Done (Inc 8):** graph renders the incident; states are clean.
- **P8 — Cleanup & production-readiness.** Delete superseded scaffold (placeholder dashboard/settings,
  `page-placeholder`, stale `runs/` sample if unused); Dockerfiles (web + worker); healthcheck;
  README/run docs; final lint + typecheck + tests; update §11 + memory.
  **Done:** no dead code; cold `docker compose up` + dev servers reproduce the demo.

---

## 8. How to run (kept current)
```
# infra
docker compose up -d                        # redis :6380, postgres :5433 (compose maps host ports)
cp .env.example .env                         # set GEMINI_API_KEY (optional: BIGGY_FAKE_RUN=1 for keyless demo)
# engine + worker (editable install with the worker extra)
src/cli/.venv/Scripts/python -m pip install -e "src/cli[worker]"
src/cli/.venv/Scripts/python -m biggy.worker # consumes biggy:jobs
# web
cd src/web && pnpm install && pnpm db:push    # apply Drizzle schema
pnpm dev                                      # http://localhost:3000/investigations
```

## 9. Non-goals (Phase 2)
Auth/multi-tenant (schema leaves room for `user_id`); engine reasoning changes (we render what the
engine emits); the `idx:incidents` vector index (lands with engine Inc 5); horizontal scaling beyond
a single worker; web CI (added opportunistically).

## 10. Risks & decisions
- **Two-language schema drift** → keep the job payload tiny; worker validates incoming jobs with
  Pydantic; a test asserts TS event types == `trace.py` `EVENT_*`. This doc is the single source.
- **No offline LLM stub** → worker/API tests use an **injectable fake `investigate`** + compose
  services; live Gemini is a manual P5/P8 smoke (skipped without a key, like the engine tests).
- **SSE needs Node-server mode** (`next start`/`next dev`), not edge/serverless. Deploy accordingly.
- **Status color** lacks a token (only `--destructive`) → add `--success/--warning/--info`; status
  surfaces are token-driven, never per-component hex.
- **Schema ownership** = Drizzle (migrations); the worker writes rows only.
- **RSC/client boundary** → presentational components stay import-clean so they render in both contexts.

## 11. Progress log (update as phases land)
- [x] P0 — Foundations & contracts — compose healthy; contracts.ts ↔ worker/contracts.py (parity test) + zod v4; web deps + worker extra installed; 6 shadcn primitives added; `--success/--warning/--info` tokens; tsc clean.
- [x] P1 — Engine trace seam — `tool_result`/`verdict` emits + `should_cancel` hook; offline seam test (FakeLLM); CLI byte-unchanged; 25 pytest green.
- [x] P2 — Persistence (Postgres) — Drizzle schema applied (`db:push`); `worker/db.py` writer; `lib/db/queries.ts`; worker-db round-trip test green against compose Postgres.
- [x] P3 — Worker — redis_io (consumer group + blocking claim) · RedisPgSink · runner (injectable investigate) · fake.py (real vault + verifier) · `python -m biggy.worker`; offline e2e tests green.
- [x] P4 — Walking skeleton (e2e, poll) — composer + server action (INSERT+XADD) · RSC list/detail · briefing tree (mirrors render.py) · shared atoms. Verified in-browser: trigger → worker → grounded briefing (✓3/3) + history row.
- [x] P5 — Live trace (SSE) — `/events` route (replay PG → tail Redis, Last-Event-ID) · `use-event-stream` · `LiveRun` reducer · trace panel + tabs. Verified in-browser: full streamed timeline + briefing resolve, no polling.
- [x] P6 — Tangible grounding (citations → source) — `/api/source` (access-bounded vault read) · source-viewer Sheet + context · interactive citation chips · tool-call audit tab. Verified in-browser: citation → diff at the cited line.
- [x] P7 — Graph & states — `/api/topology` + blast-radius SVG (cause lit, herring greyed; 6-node subgraph verified) · history filters · cancel button · copy-briefing + sonner · failed-state surfacing · reduced-motion.
- [x] P8 — Cleanup & production-readiness — deleted scaffold (page-placeholder, detail-poller, settings) + cleaned nav; `/api/healthz`; standalone prod build green; Dockerfiles (web + worker) + `.dockerignore`; eslint + ruff + 32 pytest + tsc all green; READMEs refreshed.
