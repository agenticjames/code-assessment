# Biggy

An AI on-call incident-investigation copilot. It takes a vague production incident, investigates a
workspace of operational evidence, and produces a **briefing you can trust**: ranked hypotheses with
calibrated confidence, the red herring ruled out *with a reason*, and every claim verified against
its source by deterministic code. See [`docs/DESIGN.md`](docs/DESIGN.md) for the thesis and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for how it's built.

## Layout

```
biggy/
├─ docs/          # design · architecture · delivery plan · dataset
├─ workspaces/    # the data vault — acme-checkout (topology, runbooks, telemetry, scenarios)
└─ src/
   ├─ cli/        # Python: the investigation engine + `biggy` CLI (Phase 1) — see src/cli/README.md
   └─ web/        # Next.js app over the same engine (Phase 2) — see src/web/README.md
```

| Package | What |
|---|---|
| [`src/cli`](src/cli) | The engine + CLI: time-scoped evidence, an abductive (hypothesize → disconfirm → adjudicate) loop, a deterministic citation verifier, and an eval harness. **The runnable Phase 1.** |
| [`src/web`](src/web) | Next.js + shadcn front end that triggers the engine and streams its reasoning (Phase 2). |

## Quick start — the CLI

```powershell
cd src/cli
python -m venv .venv
.venv\Scripts\Activate.ps1        # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
# create a repo-root .env with your GEMINI_API_KEY (see .env.example), then:
biggy investigate "checkout is throwing 504s and customers are complaining" -s A --check
```

The full guide is [`src/cli/README.md`](src/cli/README.md).

## Quick start — the web app (Phase 2)

The web app drives the **same engine** the CLI does, via a Redis queue + a Postgres store and a
Python worker. Architecture + build plan: [`docs/PHASE2.md`](docs/PHASE2.md).

```bash
docker compose up -d                                 # Redis :6380 + Postgres :5433 (healthchecked)
cp .env.example .env                                  # set GEMINI_API_KEY (see .env.example)
pip install -e "src/cli[worker]"                      # engine + worker deps (redis, psycopg)
pnpm -C src/web install && pnpm -C src/web db:push    # apply the Drizzle schema
python -m biggy.worker                                # terminal 1: consume biggy:jobs
pnpm -C src/web dev                                   # terminal 2: http://localhost:3000/investigations
```

See [`src/web/README.md`](src/web/README.md).

## Conventions

- **`src/cli`** is a pip/venv Python package (`pyproject.toml`); **`src/web`** is a pnpm/Node package.
- Each package under `src/` is self-contained (its own manifest, dependencies, and config).
