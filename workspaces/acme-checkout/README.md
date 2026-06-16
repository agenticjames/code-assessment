# Acme Checkout — Investigation Workspace

A synthetic but internally-consistent operational world for an e-commerce stack. **One standing
company, one continuous operational history, many investigations.** There are no pre-sorted
"incident folders" — the agent investigates by slicing a shared, time-indexed corpus, exactly as
an on-call engineer queries a log/metrics backend.

## Layout

- **Standing knowledge** (discrete, timeless docs): `topology/`, `teams.yaml`, `slos.yaml`,
  `monitors/`, `adr/`, `runbooks/`, `incident-library/`, `GLOSSARY.md`.
- **`telemetry/`** — the **continuous, time-indexed operational history** (2026-06-08 → 06-16, UTC),
  sliceable by `[from,to]` + service:
  - `logs/<service>.log` — one rolling log per service · `metrics/<metric>.csv` — continuous series
  - `alerts.jsonl` — the full alert stream · `deploys.yaml` — the full change history · `changes/` — diffs
  - `chat/incidents.md` — the rolling `#incidents` transcript · `captures/` — point-in-time tool dumps
  - `support-tickets.md`, `status-updates.md`
- **`scenarios/<X>/`** — thin **eval pointers**, NOT data: `query.yaml` (the question + `as_of`/`range`)
  + `HIDDEN_TRUTH.md` (the graded answer key, **never fed to the agent**). All evidence lives in
  `telemetry/`.

## How an investigation works

A query carries either an **`as_of`** (a live page — investigate as-of that moment, looking back) or a
**`range`** (a retrospective "what happened between X and Y"). The engine slices `telemetry/` to that
window + the relevant services; the tools (`get_changes`, `get_metric`, `read_file`, `search`) do the
scoping. **`as_of` clamps visibility** so the agent never sees the future (e.g. the war-room conclusion
that comes later) — it must derive the answer, not read it.

> Try it: `investigate "<query>" --workspace acme-checkout --scenario <A|B|C|D|E|F|G>`
> or open-ended: `investigate "why did checkout get slow last week?" --as-of 2026-06-16T12:00:00Z`

## The world at a glance
~21 services across edge / core / platform / data / external (`topology/services.yaml`).
Load-bearing detail: **`rate-limiter`, `checkout`, `cart` share one Redis pool** (`max_connections: 50`,
see `adr/ADR-014-shared-redis.md`); **`auth-service` is an upstream of ~8 services** (high fan-in);
`payment-gateway` is third-party.

## Example queries → what a good investigation produces  (the eval set)

| # | Query (`scenarios/<X>/query.yaml`) | as_of / range | Should conclude | The tell |
|---|---|---|---|---|
| **A** | *"checkout is throwing 504s and customers are complaining"* | as_of 06-16 15:15 | rate-limiter `dep-7e2a` (`max_tokens 100→10`) exhausted the shared Redis pool (50/50) → 504s. **~0.8.** Rules out the 14:00 orders-db migration (rollback @14:58 didn't help; DB latency flat). Drops the chronic disk SEV4. | rejects the migration that symptom-keywords **and** the Slack consensus point to; may recall **INC-0987** |
| **B** | *"~20 alerts, what's actually going on?"* | as_of 06-10 21:18 | one root — `auth-service` OOM/crashloop after `dep-3a8c` cut memory 2Gi→1Gi; the other ~19 are downstream symptoms | finds auth though it's neither the first nor loudest alert — by grouping on the shared upstream |
| **C** | *"intermittent 500s for the last hour, can't reproduce"* | as_of 06-15 17:00 | **inconclusive ~55/45** (orders memory/GC vs. flaky downstream); names the missing evidence (GC logs, traces). **Must not** declare one cause | stays calibrated under pressure |
| **D** | *"orders failing with connection errors again"* | as_of 06-12 10:20 | shared-Redis-pool exhaustion under a promo surge; **matches INC-0987** (same class/fix) by *meaning* | semantic recall where keyword search wouldn't fire |
| **E** | *"error rate spiked right after this morning's deploy"* | as_of 06-16 08:39 | `dep-5b71` (search) regression. **>0.9.** Recommend rollback | decisive on clean evidence — no manufactured doubt (complement to C) |
| **F** | *"checkout getting slower over the past few days"* | as_of 06-16 12:00 | a gradual memory-leak / saturation read off a multi-day trend; **no recent deploy correlates** | trend reasoning; resists forcing a deploy-correlation (as_of is before A's spike, so p99 shows only the creep) |
| **G** | *"why was checkout unstable between June 10 and June 12?"* | range 06-10…06-12 | a **timeline of two distinct incidents** — B (auth, 06-10) + D (redis, 06-12) — not one root cause; nothing from 06-16 | range reasoning over the continuous corpus; correct time-scoping |

## What the agent may read (access boundary)
The agent's evidence access is rooted at **`telemetry/` + the standing knowledge** (`topology`,
`teams`, `slos`, `monitors`, `adr`, `runbooks`, `incident-library`, `GLOSSARY`). The **entire
`scenarios/` tree is harness-only and is never exposed to the agent's tools** — *both* files are
things the **harness** uses, not the agent:
- the orchestrator reads `query.yaml` to **pose** the query (+ `as_of`/`range`); the agent receives
  the query as its task input — it does **not** read the file;
- the eval grader reads `HIDDEN_TRUTH.md` to **score**; the agent never sees it.

Enforce in the engine, not by convention: (1) the agent's evidence root **excludes `scenarios/`**;
(2) a path denylist on `read_file`/`search`/`list_evidence` as belt-and-suspenders; (3) a unit test
asserting the agent cannot open anything under `scenarios/`. (`incident-library/` stays reachable —
it's the semantic-memory corpus, not an answer key.)

## Grading
`HIDDEN_TRUTH.md` in each scenario encodes the gradeable expectations (root cause / inconclusive /
multi-incident, herring, noise to drop, required citations into `telemetry/`, confidence ranges,
missing-evidence list). The eval harness scores each run against it.

## Realism — fixture vs. live systems (known simplifications & future work)

This workspace is a **reproducible fixture** standing in for the live backends a real org runs:
Datadog/Splunk/Loki (logs), Prometheus/Grafana (metrics), Alertmanager/PagerDuty (alerts), CI/CD +
git (deploys/diffs), Slack (chat), Backstage/CMDB (topology), incident.io/Confluence (runbooks &
post-mortems), Zendesk/Statuspage (tickets/status). Every file mirrors a real artifact, and the
agent's tools (`get_metric`, `get_changes`, `search`, `read_file`, `recall_similar_incidents`) are
shaped like **queries** — so swapping this fixture for live or ingested backends is a *data-source*
change that leaves the agent logic unchanged. The data is deliberately **scaled down and cleaned**
for determinism and reviewability; it is realistic in *kind*, not in *scale*.

Known simplifications, and where we'd take it with more time:

- **Volume / signal density.** Real logs & metrics are orders of magnitude larger and noisier; here
  a signal line sits among dozens, not millions. *Future:* push filtering down into the tools
  (return windowed/grepped slices) so the access pattern scales regardless of corpus size; optionally
  grow a couple of streams toward production volume.
- **Pristineness.** No gaps, clock skew, dropped spans, or malformed lines. *Future:* inject a little
  realistic mess (a metric gap, a partial/garbled log line, unrelated-service noise) — which also
  exercises the engine's failure-handling.
- **Metric cadence.** Mixed coarse/fine here; a real scraper emits a constant interval. *Future:*
  constant-cadence series (or document the downsample explicitly).
- **Solvable-by-design.** The runbook/ADR/chat/captures line up neatly; real investigations carry
  more missing context (Scenario C is the deliberate exception). *Future:* more partial-evidence cases.
- **World scale.** ~21 services / ~10 prior incidents (a small org). *Future:* scale topology and the
  incident-library toward enterprise size to stress graph traversal and semantic retrieval.
- **Live integration.** *Future:* back the same tool interface with real Datadog/Prometheus/Slack/
  PagerDuty connectors, so the engine runs unchanged against a production estate.
