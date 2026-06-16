# Synthetic Dataset — Authoring Blueprint

> Companion to [`DESIGN.md`](DESIGN.md) and [`DELIVERY.md`](DELIVERY.md).
> **DESIGN = the *what*** (product, architecture). **DELIVERY = the *when*** (build order).
> **This = the *data to author*** — the synthetic world the agent investigates, and the eval set that grades it.
>
> **Status:** BUILT, then RESLICED. The dataset exists under `workspaces/acme-checkout/`.
>
> ⚠️ **Architecture update (supersedes the per-scenario folder layout in §2 below).** Evidence is
> no longer partitioned per scenario. It now lives in ONE continuous, time-indexed corpus at
> `workspaces/acme-checkout/telemetry/` (per-service `logs/`, continuous `metrics/`, one
> `alerts.jsonl`, one `deploys.yaml`, `changes/` diffs, a rolling `chat/incidents.md`, `captures/`,
> `support-tickets.md`, `status-updates.md`). A "scenario" is now a **thin eval pointer** —
> `scenarios/<X>/query.yaml` (the question + an `as_of` timestamp or a `range`) + `HIDDEN_TRUTH.md`
> (the graded key). The agent slices the corpus by time+service; `as_of` clamps visibility so it
> can't see the future. This makes open-ended range queries ("why did it go down between X and Y")
> answerable — see scenario **G**. The §0 richness philosophy and §5–§7 (scenarios, HIDDEN_TRUTH
> schema, coverage) still hold; only the *storage layout* changed. Authoritative orientation +
> eval set: `workspaces/acme-checkout/README.md`.

---

## 0. The thesis — what "rich" means here (and what it must not)

The brief is explicit:

> *"You do not need a large dataset. A small but realistic dataset with enough ambiguity, noise, and signal is better than a huge artificial one."*

So **richness is not volume.** A 10,000-line log dump reads as *overbuilt* and buries the signal — exactly the trap the brief penalizes. Our dataset is rich along five axes a reviewer actually rewards, and **disciplined in line count**:

| Axis of richness | What it means | Why a reviewer rewards it |
|---|---|---|
| **Breadth of evidence *types*** | Cover ~all 13 inputs the brief lists (§8) | Signals thoroughness; doing it small signals judgment |
| **Causal depth** | The answer is a *multi-hop chain across files*, never stated in one | Forces *reasoning*, not grep — the non-theater proof |
| **Texture realism** | Real log formats, alert JSON, stack traces, human chat mess | Reads as a real on-call world, not a toy |
| **Airtight consistency** | Every name/time/ID/metric lines up across every file | The one thing that instantly betrays a synthetic set if wrong |
| **Deliberate negative space** | Planted *missing* evidence, noise to drop, herrings with alibis | Where calibration & honest uncertainty get tested |

**Rule of thumb:** if a file doesn't add a *type*, a *hop in a causal chain*, *texture*, or *deliberate negative space*, it's padding — cut it.

---

## 1. Locked decisions

- **One workspace** — `acme-checkout` (an e-commerce stack). A second workspace is *not* built; it's noted as a future generalization multiplier (§11).
- **Timezone: UTC everywhere.** Stated in `workspace.yaml`. (A timezone-confusion clue, if ever used, must be *deliberate* and documented in `HIDDEN_TRUTH`.)
- **Date anchor:** today = **2026-06-16**. Live incidents dated within June 2026 (flagship **A** pinned to `2026-06-16`). Incident-library post-mortems spread across the prior **~6 months** (≈ 2025-12 → 2026-06).
- **6 scenarios, tiered** (§5): A B C D rich, E F lean; G specced as a stretch.
- **`HIDDEN_TRUTH.md`** per scenario = machine-gradeable answer key, **never fed to the agent** (§7).
- A human-readable **dataset `README.md`** doubles as the demo script + eval set (§9, drafted drop-in in Appendix A).

---

## 2. Folder structure

`workspaces/` is the root container (supports N workspaces; we build one). Value-add evidence types beyond DESIGN §3.1 are marked ★.

```
workspaces/
└─ acme-checkout/
   ├─ README.md                      # ★ orientation + example queries → expected outcomes (the eval set; Appendix A)
   ├─ workspace.yaml                 # name, domain, environment, conventions, timezone=UTC, date anchor
   ├─ GLOSSARY.md                    # ★ service/acronym/term dictionary (world realism + agent aid)
   ├─ topology/
   │   └─ services.yaml              # ~20-service dependency graph — the lightweight knowledge graph (§3)
   ├─ teams.yaml                     # ownership, on-call rotation, escalation, Slack channels
   ├─ slos.yaml                      # ★ SLO + error-budget defs (grounds severity & the stakeholder note)
   ├─ adr/
   │   └─ ADR-014-shared-redis.md    # ★ WHY rate-limiter + checkout share Redis (the trap's origin story)
   ├─ monitors/
   │   └─ alert-rules.yaml           # ★ alert thresholds (lets the agent reason WHY an alert fired, not just THAT)
   ├─ runbooks/
   │   ├─ redis-connection-pool.md   # load-bearing breadcrumb: shared pool, 50-cap, throttle→exhaustion
   │   ├─ rate-limiter-operations.md # what max_tokens does + safe ranges (so 10 reads as "too low")
   │   ├─ checkout-oncall.md
   │   ├─ auth-service.md            # for Scenario B
   │   └─ deploy-rollback.md
   ├─ incident-library/              # the SEMANTIC-MEMORY corpus — ~10 prior post-mortems (§4)
   │   ├─ INC-0987-redis-pool-flash-sale.md     # the TRUE match for the pool-exhaustion class
   │   ├─ INC-1042-redis-latency-az.md          # near-miss (Redis keyword, different cause)
   │   ├─ INC-1108-checkout-504-bad-image.md    # near-miss (504/checkout keyword, deploy regression)
   │   └─ ... (decoys + cross-ties — full list in §4)
   └─ scenarios/
      ├─ A-checkout-504/             # RICH — flagship
      │   ├─ scenario.yaml           # query, time_window, severity
      │   ├─ HIDDEN_TRUTH.md         # machine-gradeable key (NOT fed to agent)
      │   ├─ alerts/alerts.json      # Alertmanager-shape firing alerts
      │   ├─ logs/{api-gateway,checkout,redis,rate-limiter,orders-db,log-aggregator}.log
      │   ├─ metrics/{checkout_p99,redis_connections,ratelimit_rejects,orders_db_latency}.csv
      │   ├─ traces/checkout-req-trace.json      # ★ OTel-style span waterfall (timing discriminator)
      │   ├─ changes/deployments.yaml
      │   ├─ changes/rate-limiter.config.diff
      │   ├─ changes/rate-limiter.config.yaml    # ★ current state (read config, not just the diff)
      │   ├─ tool-outputs/redis-cli-info.txt     # ★ mock API: connected_clients:50/maxclients:50 (smoking gun)
      │   ├─ tool-outputs/kubectl-get-pods.txt   # ★ synthetic tool output
      │   ├─ chat/incident-war-room.md
      │   ├─ tickets/customer-impact.md          # ★ support tickets + $ impact
      │   └─ comms/status-page-draft.md          # ★ a WRONG draft blaming the DB (cost of the herring)
      ├─ B-alert-storm/      # RICH  (see §6)
      ├─ C-intermittent-500/ # RICH  (see §6)
      ├─ D-recurring/        # RICH  (see §6)
      ├─ E-deploy-regression/  # LEAN (see §6)
      └─ F-slow-burn/          # LEAN (see §6)
```

---

## 3. Topology — one graph that serves every scenario

`topology/services.yaml` is the load-bearing artifact: the dependency graph the agent **traverses as a tool** (not a graph DB). ~20 services across **edge / core / platform / data / external** tiers. A single topology serving all six incidents is itself the anti-overfitting proof.

**Engineered constraints** (everything else is realistic filler):

| Constraint | Serves | Why |
|---|---|---|
| `redis` → `max_connections: 50`, `shared_by: [rate-limiter, checkout, sessions]` | **A**, **D** | The bridge that lets the agent connect throttle → pool → checkout |
| `auth-service` is a dependency of ~8 services (high fan-in) | **B** | Storm collapse = grouping alerts by shared upstream |
| `payment-gateway` → `external: true` (3rd-party) | **C** | A plausible flaky-dependency candidate |
| `orders-db` is checkout's *direct* dep | **A** | Makes the DB-migration herring topologically plausible |
| `kafka` between `orders` and downstream processing | **C**, **F** | Lag / leak candidates |

**Service inventory (~20):** `api-gateway`, `cdn` *(edge)* · `checkout`, `orders`, `cart`, `search`, `recommendations`, `user-profile`, `notifications`, `inventory` *(core)* · `rate-limiter`, `auth-service`, `feature-flags` *(platform)* · `redis`, `orders-db`, `sessions-store`, `search-index`, `kafka` *(data)* · `payment-gateway`, `shipping-api`, `email-provider` *(external)*.

Per-service fields: `tier`, `depends_on[]`, `owner` (team), `slo` (pointer to `slos.yaml`), optional `config` pointer, and data-store specifics (`max_connections`, `type`, `shared_by[]`).

**Teams (`teams.yaml`):** `team-payments` (checkout) · `team-platform` (rate-limiter, redis, feature-flags, api-gateway) · `team-identity` (auth-service, sessions, user-profile) · `team-data` (orders-db, kafka, search-index) · `team-growth` (recommendations, search, notifications) · `team-fulfillment` (inventory, shipping). Each with on-call name, escalation, Slack channel.

---

## 4. Incident-library — the semantic-memory corpus

This is where embeddings earn their keep, so it's **engineered for vocabulary diversity**, not volume. ~10 short structured post-mortems (~30–50 lines each: title, date, symptoms, root cause, resolution, fix, tags), in three deliberate buckets:

| ID | Date | Title | Bucket | Purpose / cross-tie |
|---|---|---|---|---|
| **INC-0987** | 2026-02 | Redis connection saturation during flash sale | **TRUE match** | Pool exhaustion in *different words* ("ran out of available connections", "promo surge") — fires on **A** & **D** where keyword search fails |
| INC-1042 | 2026-04 | Redis latency spike (AZ network partition) | Near-miss | Shares "Redis" keyword, **different cause** — proves retrieval discriminates on meaning |
| INC-1108 | 2026-05 | Checkout 504s after bad container image | Near-miss | Shares "504/checkout" with **A**, but cause = deploy regression (could be confused with A or E) |
| INC-1095 | 2026-05 | auth-service OOM after memory-limit change | Cross-tie | A *prior* auth OOM → recall can enrich **B** |
| INC-1077 | 2026-04 | Kafka consumer lag delays order processing | Cross-tie | Recall candidate for **C** (H2) / **F** |
| INC-1003 | 2026-03 | Disk full on log-aggregator | Cross-tie | Explains *why* people ignore the chronic disk alert in **A** (real past incident) |
| INC-0931 | 2025-12 | TLS cert expiry on payment-gateway | Decoy | Corpus realism — must be *rejected* by retrieval |
| INC-0955 | 2026-01 | Upstream DNS resolution failures | Decoy | Corpus realism |
| INC-0912 | 2025-12 | search-index hot shard | Decoy | Corpus realism |
| INC-1120 | 2026-06 | feature-flag misconfig broke checkout | Decoy-ish | Recent + checkout keyword, unrelated cause |

The cross-ties (1095→B, 1077→C, 1003→A) make the corpus feel like a real company's history and create recall opportunities across multiple scenarios — richness at near-zero extra cost.

---

## 5. The scenarios — capability matrix

Each scenario must add a **distinct row to the eval scorecard** — that's the discipline that keeps "very rich" from becoming padded. Scenarios are *test cases*, not extra product surface.

| # | Incident | Distinct capability proven | Tier |
|---|---|---|---|
| **A** | checkout 504s (rate-limiter → Redis pool; DB-migration herring) | Multi-hop grounded reasoning · reject herring · resist human consensus | **Rich** |
| **B** | ~20-alert storm (auth cascade) | Signal-from-noise *at scale* — storm dedup via the topology graph | **Rich** |
| **C** | intermittent 500s, can't reproduce | Calibrated **uncertainty** — knows when it *can't* tell; names missing evidence | **Rich** |
| **D** | recurring incident | Semantic **memory** — recall & cite a prior incident on a *meaning* match | **Rich** |
| **E** | clean deploy regression | Calibrated **confidence** — decisive + concrete rollback when evidence is clean | **Lean** |
| **F** | slow-burn saturation | **Trend** reasoning — gradual degradation, *no deploy to blame* | **Lean** |

**Why this exact set** (each cell is non-overlapping):
- **C ↔ E** are a matched pair — *appropriately unsure* and *appropriately decisive*. C alone invites the skeptic's "your agent just always hedges"; E refutes it.
- **A/B/E** are sharp-onset *event-correlation*; **F** is the opposite *trend* mode (read a slope, resist forcing a deploy-correlation).
- **B** is scale; **D** is memory; **A** is the flagship multi-hop.

**Tiering is the unlock:** A–D get full multi-file vaults (the rich texture). E and F get **lean vaults** (~4–6 files) — they each prove *one* capability, so they need less. This reaches six distinct capabilities at low marginal cost.

**Dial (you own it):** floor 5 (drop F) · **recommended 6** · ceiling 7 (+ **G: multi-factor / AND-gated contributing causes** — the one genuinely new capability beyond the six, highest authoring risk → spec as stretch, build only if A–F land clean). *Not* adding "benign/self-resolved" or "human-action" scenarios — they overlap A's noise-drop and C's restraint (padding).

---

## 6. Per-scenario level design

For each: the **breadcrumb trail** (reconstructible across files, never stated in one — DESIGN §3.3) and the files that carry it. Each trail below has been traced end-to-end to confirm it's *solvable* and *not given away*.

### A — "checkout is throwing 504s and customers are complaining" (RICH, flagship)

**Causal chain (7 hops):**
```
504s @14:47 (alerts, api-gw log, checkout_p99)
  → checkout.log "timeout waiting for connection"  → LOOKS like orders-db   (TRAP)
  → topology: checkout & rate-limiter SHARE redis (max 50)                  [graph hop]
  → changes: TWO in window — migration @14:00 (herring) + rate-limiter dep-7e2a @14:45
  → TIMING: migration done 14:12 (35-min gap ✗); deploy 14:45 → onset 14:47 (✓)
  → mechanism: rate-limiter.config.diff  max_tokens 100→10
  → redis.log "max number of clients reached (50/50)" + redis-cli connected_clients:50/50
  → runbook redis-connection-pool.md documents throttle-misconfig → pool exhaustion
  → metrics: redis_connections pegs 50 @14:47; ratelimit_rejects spike
```
- **Herring + alibi:** `orders-db.log` + `orders_db_latency.csv` show the migration completed clean @14:12 and the DB stayed healthy; `deployments.yaml` records a **failed rollback @14:58** — and 504s *continued* after it. Hard proof of innocence.
- **Dismissed-but-correct human clue:** in `chat/`, `dana` blames the migration and rolls back; `priya` notes the latency lines up with the rate-limiter deploy, **and gets talked over**.
- **True noise:** chronic `disk-space SEV4` on `log-aggregator` (firing for days; `sam`: "ignore it, log-aggregator always does that") — must be *explicitly* dropped. (Tied to INC-1003.)
- **Memory hook:** matches **INC-0987** (pool exhaustion, same fix).
- **Richness payoffs:** `traces/checkout-req-trace.json` shows a failing request burning its budget on the `rate-limiter → redis` span; `redis-cli-info.txt` is the smoking gun; `comms/status-page-draft.md` is a *wrong* draft blaming the DB (the agent correcting it = stakeholder-note payoff).
- **Date:** 2026-06-16, window 13:30–15:30 UTC.

### B — "we're getting paged by ~20 alerts, what's actually going on?" (RICH)

**Root:** `auth-service` degrades (OOM → crashloop) → every service calling auth throws 401s/timeouts → 19 downstream alerts + 1 root.
- **Level-design art:** the auth alert is **buried** — *not* the loudest, and (realistically) fires *slightly after* some downstream alerts (detection lag). "First alert" and "most alerts" heuristics both fail; only **grouping by shared upstream dependency** collapses it.
- **Files:** `alerts/alerts.json` (~20 across checkout/orders/cart/search/recommendations/user-profile/notifications — 401/timeout/latency; one auth `OOMKilled`) · `logs/auth-service.log` (memory-limit hit → OOM → restart loop) · a trigger in `changes/` (config change lowering the memory limit) · a couple downstream logs (`checkout.log`, `orders.log` with "auth check timed out") · `chat/` ("everything's down!" → the methodical "*wait — every one of these calls auth*").
- **Memory hook:** INC-1095 (prior auth OOM).

### C — "intermittent 500s for the last hour, can't reproduce" (RICH, calibration showcase)

**Genuinely ambiguous** — two live hypotheses the evidence *cannot* separate:

| Hypothesis | Supporting evidence *present* | Discriminating evidence **deliberately absent** |
|---|---|---|
| H1: `orders` memory pressure → periodic GC stalls → 500s | memory sawtooth metric; 500s loosely cluster near memory peaks | **GC logs / heap dumps** |
| H2: flaky downstream (kafka/payment) → timeout → 500s | 500s on the order-placement path; sporadic, irregular | **downstream logs + traces** for the window |

- `changes/` shows **nothing deployed recently** (kills the easy answer). `chat/` shows two genuinely split camps, no resolution.
- **Correct output:** ~55/45, *both* hypotheses named, **the exact missing evidence stated**, never a fabricated root cause.
- `HIDDEN_TRUTH` documents the omissions so the eval grades **calibration**, not correctness.

### D — "orders are failing with connection errors again" (RICH, memory showcase)

A fresh recurrence whose symptom signature **semantically matches INC-0987** in *different vocabulary* (so keyword search fails, semantic wins). Proves `recall_similar_incidents` retrieves & cites the prior fix ("matches INC-0987, same class, same fix"). Keep the vault lean — it reuses the A-class failure shape; its job is to make recall fire on *meaning*.

### E — "error rate spiked right after this morning's deploy" (LEAN, confident anchor)

**Clean, confirmable, decisive.** A deploy `dep-XXXX` at T introduced a regression (e.g., a removed null-check / bad query) → 500s climb *immediately*; single service; **no shared-infra twist, no herring.**
- **Files (lean):** `changes/deployments.yaml` (the deploy) · one service log with a clear stack trace introduced at T · `error_rate.csv` (flat → step-change at T) · the commit diff · `chat/` where a rollback **fixes it** (confirmation).
- **Correct output:** HIGH confidence (>0.9), single hypothesis, concrete action "roll back `dep-XXXX`", **no manufactured doubt** — the inverse failure mode of C.

### F — "checkout has been getting slower over the past few days, no idea why" (LEAN, trend)

**Slow-burn saturation** — a gradual resource leak (connections/file-descriptors/memory creeping over days). **No recent deploy correlates** — the cause is a *trend*, found only by reading a multi-day slope.
- **Files (lean):** a multi-day metric CSV with a clear upward trend · `deployments.yaml` showing an empty recent window (the "no deploy" tell) · a log showing slowly-growing resource use · a runbook on the leak class · optional tie to a library incident.
- **Correct output:** identifies the trend, **explicitly notes no deploy correlates → gradual saturation**, recommends the capacity/leak remediation.

---

## 7. `HIDDEN_TRUTH.md` schema (machine-gradeable)

The eval harness (DELIVERY Inc 4) and the citation verifier depend on this. Structured front-matter, not prose. **Never fed to the agent.**

```yaml
# scenarios/A-checkout-504/HIDDEN_TRUTH.md
outcome: root_cause                       # root_cause | inconclusive
root_cause:
  service: rate-limiter
  mechanism: "max_tokens 100→10 → shared Redis pool (50/50) exhaustion → checkout 504s"
herring:
  service: orders-db
  disconfirm: ["failed rollback @14:58 didn't fix 504s", "orders_db_latency flat through incident"]
noise_to_drop: ["disk-space SEV4 on log-aggregator (chronic)"]
required_citations:                       # substring or file:line the verifier must find
  - "changes/rate-limiter.config.diff"
  - "logs/redis.log :: max number of clients reached"
  - "changes/deployments.yaml :: dep-7e2a"
expected_confidence:                       # graded as ranges
  rate-limiter: ">=0.7"
  orders-db:    "<=0.1"
expected_open_questions: ["no canary logs for dep-7e2a"]
memory_recall: ["INC-0987"]                # for A & D
```

For **C** the key fields flip:
```yaml
outcome: inconclusive
expected_hypotheses: ["orders memory/GC", "flaky downstream (kafka/payment)"]
expected_confidence: { top: "0.45..0.60" }   # calibrated, NOT decisive
missing_evidence_named: ["GC logs / heap dumps", "downstream traces for the window"]
must_not: ["declare a single confirmed root cause"]
```

---

## 8. Evidence-type coverage map

Proving breadth without bulk — every input the brief lists (lines 49–64) has a home:

| Brief input type | Where it lives |
|---|---|
| Logs | `logs/*.log` (multi-service, mixed formats) |
| Alerts | `alerts/alerts.json` + `monitors/alert-rules.yaml` |
| Metrics snippets | `metrics/*.csv` |
| Runbooks | `runbooks/*.md` |
| Prior incident notes | `incident-library/INC-*.md` |
| Deployment notes | `changes/deployments.yaml`, `*.config.diff` |
| Service metadata | `topology/services.yaml`, `workspace.yaml` |
| Ownership info | `teams.yaml` (+ owner fields in topology) |
| Chat transcripts | `chat/incident-war-room.md` |
| Customer impact notes | `tickets/customer-impact.md` |
| Synthetic tool outputs | `tool-outputs/kubectl-get-pods.txt` |
| Mock API responses | `tool-outputs/redis-cli-info.txt`, `traces/*.json` |
| Knowledge base articles | `adr/*.md`, `GLOSSARY.md`, `slos.yaml` |

---

## 9. Texture playbook + the consistency contract

**Format realism (pick one shape per type, stay consistent):**
- **Logs:** api-gateway = access/JSON w/ request IDs + latencies; app services = logfmt or structured JSON w/ levels + stack traces; redis = its real log format. Include benign INFO spam around the signal so the agent must *filter* — the signal line is *one* line, deliberately placed.
- **Alerts:** Alertmanager shape — `labels` (service, severity, team), `annotations`, `startsAt`/`endsAt`, `fingerprint`, `status: firing|resolved`.
- **Metrics:** `timestamp,value` CSV at 30s–1m cadence; values that tell the timing story precisely.
- **Changes:** YAML event log — `id`, `service`, `type` (deploy|config|migration), `ts`, `author`, `status`, diff pointer.
- **Chat:** Slack-style `[HH:MM] user:` with bot posts (`deploybot`, `pagerduty`), typos, an "edited" note, emoji, abandoned theories.

**The three reasoning levers** (what makes it non-grep-able):
- **Multi-source corroboration in different words** — pool exhaustion appears as redis `max clients reached`, metric `redis_connections=50`, `redis-cli connected_clients:50`, *and* runbook prose. Same fact, four vocabularies.
- **Timing precision** — the 2-min vs 35-min gap is *the* discriminator in A; metric/trace timestamps must be exact.
- **Pre/post-window evidence** — the chronic disk alert *predates* onset; the failed rollback *postdates* it. Tests time-scoping; adds realism.

**The consistency contract (the world bible — author against a single facts table):**
- One timezone (**UTC**), stated. One date anchor (**2026-06-16**).
- Consistent ID schemes: `INC-####`, `dep-####` (e.g. `dep-7e2a`), alert `fingerprint` hex, request IDs, ticket `ZD-####`.
- Service / team / person names identical everywhere they appear, and every service named in a log/alert exists in `topology/services.yaml`.
- Consistent metric names + units. Recurring cast: `dana` (team-data), `priya` (team-platform), `sam` (team-platform/SRE), `raj` (team-payments), `mei` (incident commander).

---

## 10. Sizing guardrails + build sequence

**Sizing (keeps "rich" from becoming "bloated"):**
- Logs: ~30–80 lines each (enough INFO to force filtering, not a haystack).
- Incident library: ~10 post-mortems, ~30–50 lines each.
- Topology: ~20 services. Lean scenarios (E, F): ~4–6 files each.
- **Total workspace: a few thousand lines across ~50–70 files** — reads as a *thoughtfully constructed world*, never a dump.
- **Determinism:** keep A/B/D/E signals unambiguous enough that a low-temp model lands them every run; keep C *robustly* ambiguous; F's trend clear. Richness must not make conclusions flaky.

**Build sequence (maps to DELIVERY):**
- **Author A fully now** — it unblocks the entire walking skeleton (Inc 0–3).
- **Stub B/C/D/E/F** as `scenario.yaml` + `HIDDEN_TRUTH.md` so structure is visible; fill vaults as increments arrive.
- Inc 4 eval scorecard covers **A/B/C/E/F** (5 rows); **D** joins at Inc 5 → **6-row final scorecard** ("I measure my agent across diverse cases").

---

## 11. Stretch / future (specced, not built)

- **Scenario G — multi-factor / AND-gated contributing causes:** the 7th distinct capability; build only after A–F land clean.
- **Second workspace** (e.g. a data-streaming / Kafka domain): the true generalization multiplier (DESIGN §2). The `workspaces/` container already supports it; building it is a *with-more-time* item, not in scope now.

---

## Appendix A — the dataset `README.md` (drop-in)

> Drop-in content for `workspaces/acme-checkout/README.md`. Doubles as **orientation**, the **demo script** (copy-paste queries), and a **human-readable eval set** (the machine-gradeable keys live in each scenario's `HIDDEN_TRUTH.md`).

```markdown
# Acme Checkout — Investigation Workspace

A synthetic but internally-consistent operational world for an e-commerce stack,
used to exercise the incident investigator. **One standing workspace, many incidents.**

- **Standing world** (changes rarely): `topology/`, `teams.yaml`, `slos.yaml`,
  `runbooks/`, `adr/`, `monitors/`, `incident-library/`.
- **Scenarios** (time-bounded incidents to investigate): `scenarios/<X>/`.
- **Conventions:** all timestamps **UTC**; IDs `INC-####`, deploys `dep-####`,
  tickets `ZD-####`. Each scenario's `HIDDEN_TRUTH.md` is the graded answer key and
  is **never given to the agent**.

## The world at a glance
~20 services across edge/core/platform/data/external. Load-bearing detail:
`rate-limiter` and `checkout` **share one Redis instance** (`max_connections: 50`)
— see `adr/ADR-014-shared-redis.md`. `auth-service` is an upstream dependency of
~8 services. `payment-gateway` is a third party.

## Example queries → what a good investigation produces  (the eval set)

> Run: `investigate "<query>" --workspace acme-checkout --scenario <X>`

### A · `scenarios/A-checkout-504`   ★ flagship
- **Query:** *"checkout is throwing 504s and customers are complaining"*
- **Should conclude:** root cause = **rate-limiter config change** (`dep-7e2a`,
  `max_tokens 100→10`) exhausting the **shared Redis connection pool (50/50)** →
  checkout can't acquire connections → 504s. **Confidence ~0.8.**
- **Should rule out:** the **orders-db migration** (timing gap + the failed rollback
  @14:58 didn't fix it). **Should drop:** the chronic disk-space SEV4 noise.
- **Should cite:** `rate-limiter.config.diff`, `redis.log` "max clients reached",
  `deployments.yaml` `dep-7e2a`, `redis-cli` info.
- **The tell (proves reasoning, not pattern-match):** rejects the migration that
  both the symptom keywords *and* the Slack consensus point to.

### B · `scenarios/B-alert-storm`
- **Query:** *"we're getting paged by ~20 alerts, what's actually going on?"*
- **Should conclude:** **one root** — `auth-service` degradation (OOM/crashloop);
  the other ~19 alerts are **downstream symptoms** of services that depend on auth.
- **Should recommend:** focus on auth-service; the rest will clear when it recovers.
- **The tell:** finds auth even though it isn't the loudest or first alert — by
  grouping alerts on their shared upstream dependency.

### C · `scenarios/C-intermittent-500`
- **Query:** *"we've had intermittent 500s for the last hour and can't reproduce it"*
- **Should conclude:** **inconclusive — ~55/45**, two live hypotheses
  (orders memory/GC stalls vs. a flaky downstream). **Must not** declare a single
  confirmed cause.
- **Should state:** the exact missing evidence it needs (GC logs / heap dumps;
  downstream traces) and what it would pull next.
- **The tell:** stays calibrated under pressure instead of fabricating certainty.

### D · `scenarios/D-recurring`
- **Query:** *"orders are failing with connection errors again"*
- **Should conclude:** this matches a **prior incident — INC-0987** (same failure
  class, same fix), retrieved by *meaning* despite different wording.
- **The tell:** semantic recall fires where keyword search wouldn't.

### E · `scenarios/E-deploy-regression`
- **Query:** *"error rate spiked right after this morning's deploy"*
- **Should conclude:** the deploy introduced a regression. **Confidence >0.9.**
- **Should recommend:** roll back the deploy (the rollback is confirmed to fix it).
- **The tell:** decisive when the evidence is clean — no manufactured doubt
  (the complement to C).

### F · `scenarios/F-slow-burn`
- **Query:** *"checkout has been getting slower over the past few days, no idea why"*
- **Should conclude:** a **gradual resource leak / saturation** (read off a multi-day
  trend), **not** any single event — explicitly notes **no recent deploy correlates.**
- **Should recommend:** the capacity/leak remediation.
- **The tell:** reasons over a trend and resists forcing a deploy-correlation.

## Grading
`HIDDEN_TRUTH.md` in each scenario encodes the gradeable expectations
(root cause / inconclusive, herring to rule out, noise to drop, required citations,
confidence ranges, missing-evidence list). The eval harness scores each run against it.
```
```

---

*This blueprint is the contract for the dataset. Build `workspaces/` against it; if a file isn't justified by §0's four levers, it doesn't belong.*
