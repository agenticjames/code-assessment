# Sample Investigation — Scenario A (checkout 504s)

A real, end-to-end Biggy run: the messy input, the live tool-by-tool investigation, the grounded
briefing, and the eval grade. **Everything below is captured verbatim from an actual run** — the
trace and briefing are the CLI's own output; values come straight from the run's `ledger.json`.

> **Reproduce:** `biggy investigate "checkout is throwing 504s and customers are complaining" -s A --check`
> (local setup is in the repo README). Output is non-deterministic in wording, but the diagnosis is
> stable.

---

## 1. The input

| | |
|---|---|
| **What you type** | *"checkout is throwing 504s and customers are complaining"* |
| **Scenario** | A — SEV1, as of `2026-06-16T15:15Z`, 2h look-back (window `13:15–15:15Z`); 42 evidence files in window |
| **The world it investigates** | the `acme-checkout` workspace: a ~20-service topology, runbooks, ADRs, ~10 prior post-mortems, and time-sliced telemetry (logs, metrics, alerts, deploys) + messy human signal (a Slack war-room, support tickets, a public status draft) |
| **No hindsight** | the agent sees only evidence dated ≤ the as-of timestamp; it has to *derive* the cause, not read it |
| **The trap** | the surface symptoms *and* the Slack consensus *and* the public status draft all blame an `orders-db` migration that ran in the window — the real cause is elsewhere |

---

## 2. The investigation (live trace, verbatim)

Biggy proposes three hypotheses — including the orders-db migration (the "obvious" suspect) — then
spends its tool budget trying to **disprove** each. Every call is provoked by the previous finding:

```
>> hypothesize
  H1  rate-limiter config change (dep-7e2a) is throttling legitimate checkout traffic   (prior 0.60)
  H2  checkout is hitting connection-pool exhaustion from a dependency                   (prior 0.25)
  H3  orders-db migration (mig-0616) left latent table locks despite the rollback        (prior 0.15)
>> investigate
  step 1  get_changes()                                  → migration @14:00, rate-limiter config @14:45
  step 2  list_evidence()
  step 3  read_file(telemetry/metrics/ratelimit_rejects.csv)   → rejects 0 → 64 → 335 at 14:46–14:47
  step 4  read_file(telemetry/logs/rate-limiter.log)           → "connection acquire contention" @14:47
  step 5  read_file(telemetry/changes/dep-7e2a.diff)           → max_tokens 100 → 10
  step 6  get_topology(rate-limiter)                           → depends_on redis; dependents: checkout
  step 7  read_file(adr/ADR-014-shared-redis.md)               → checkout + rate-limiter SHARE one Redis
  step 8  read_file(telemetry/metrics/redis_connections.csv)   → 24 → 50, pegged at 50 from 14:47
  step 9: done gathering — emitting verdict
>> adjudicate
>> verify
  grounding: 5/5 claims verified
>> reconcile
```

---

## 3. The briefing (actual output)

The CLI prints these as bordered, colored `rich` panels; reproduced here with values verbatim from
the run.

```
INVESTIGATION BRIEFING  —  root cause          "checkout is throwing 504s and customers are complaining"

  The incident was caused by a rate-limiter configuration change that significantly reduced the token
  bucket size, triggering a spike in Redis connections. This saturated the shared Redis instance,
  causing connection acquisition timeouts in the checkout service.

GROUNDING (deterministic citation verifier):  5 / 5 claims verified

CUSTOMER IMPACT (deterministic, from support tickets):
  4 support ticket(s)  |  top priority URGENT  |  affected: checkout  |  first report 2026-06-16T14:51Z
  checkout outages map ~1:1 to lost orders (~$4.2k/min at peak) — see slos.yaml.

HYPOTHESIS 1 — rate-limiter        CONFIRMED      confidence 0.95
  The rate-limiter configuration change (dep-7e2a) is incorrectly throttling legitimate checkout
  traffic by saturating the shared Redis connection pool.
  supporting:
    [verified]  telemetry/changes/dep-7e2a.diff:8        "-  max_tokens: 100"
    [verified]  telemetry/changes/dep-7e2a.diff:9        "+  max_tokens: 10"
    [verified]  telemetry/logs/rate-limiter.log:45       "refill tick delayed: connection acquire contention"
    [verified]  telemetry/metrics/redis_connections.csv:91   "2026-06-16T14:47:00Z,50"

HYPOTHESIS 2 — orders-db           RULED OUT      confidence 0.05
  ruled out: the migration was rolled back at 14:58:00Z, but the 504 errors persisted — not the cause.
  contradicting:
    [verified]  telemetry/deploys.yaml:52   "roll back idx_orders_customer — 504s PERSISTED afterward"

OPEN QUESTIONS:
  - Why was the shared Redis instance not configured with per-service connection limits?
  - Did the cart service also fail during the Redis connection saturation?

RECOMMENDED ACTION:
  Revert the rate-limiter configuration change (dep-7e2a) to restore the previous max_tokens value of 100.

STATUS-PAGE CORRECTION (public draft vs evidence):
  The public status draft blames "a database migration performed this afternoon", but the evidence
  points to rate-limiter. Correct the draft before publishing.   (telemetry/status-updates.md:14)

STAKEHOLDER UPDATE (paste-ready):
  We have identified the root cause of the checkout 504 errors as a recent configuration change to the
  rate-limiter, which caused connection exhaustion in our shared Redis instance. We have high
  confidence in this finding. The next step is to revert the rate-limiter configuration.

tool calls: 8
```

## 4. Why this run matters

- **It rejected the consensus — on three surfaces.** The symptoms, the Slack war-room, *and* the
  public status draft all pointed at the orders-db migration. Biggy ruled it out *with a checkable
  reason* (the 14:58 rollback didn't stop the 504s) and the deterministic comms pass **flagged the
  status draft for correction** before it could be published.
- **Every claim is verified.** The grounding pass re-opened all five cited sources and confirmed each
  quote — `5/5`. (To see the verifier *catch* a gap, run with `--ablate telemetry/logs/redis.log`:
  hiding a source forces an ungrounded claim, the score drops, and an open question appears.)
- **It stayed calibrated.** Confidence is capped at `0.95` (never 1.0 — a triage first-pass isn't
  ground truth), the loser sits at `0.05`, and it volunteered two genuine open questions instead of
  overclaiming.

> The full machine-readable record of this run — every hypothesis, tool call, and citation with its
> `verified` flag — is in [`sample-ledger.json`](sample-ledger.json) (a copy of the run's
> gitignored `runs/acme-checkout-A/ledger.json`).
