# Runbook — rate-limiter operations

**Service:** `rate-limiter` (platform tier) · **Owner:** team-platform (on-call: priya; SRE: sam)
**Config:** `rate-limiter.config.yaml` · **Related:** `runbooks/redis-connection-pool.md`,
`runbooks/deploy-rollback.md`

## What it does
The rate-limiter throttles requests for `checkout` and `cart` using a **token-bucket** algorithm.
Each client gets a bucket; a request spends a token; tokens refill over time; when a bucket is
empty the request is rejected (and `ratelimit_rejected_total` increments). Buckets are stored in
the **shared Redis** (the same 50-connection pool used by checkout and cart — see ADR-014 and the
Redis runbook).

## `max_tokens` — the knob that matters
`max_tokens` is the **bucket size** (how many tokens a client may hold). It is the most common
thing changed during a tuning pass.

- **Safe operating range: ~50–200.** Tune within this band.
- **Higher** `max_tokens` → larger buckets → more permissive throttling.
- **Lower** `max_tokens` → smaller buckets → more aggressive throttling **and a hidden cost**:
  smaller buckets drain and refill far more often, so the limiter performs **many more bucket
  operations per second**. That **churn drives up Redis connection pressure** on the shared pool.

> **Danger:** values well *below* the safe range (e.g. `max_tokens: 10`) are recognizably unsafe.
> They cause excessive bucket churn and can push the shared Redis pool toward exhaustion, which
> shows up downstream as **checkout connection-acquisition timeouts / 504s** — not as an obvious
> rate-limiter error. A too-low `max_tokens` is a prime suspect when the Redis pool saturates.

Other fields you may see: `refill_rate` (tokens added per second), `bucket_ttl` (idle bucket
expiry). Leave these alone unless you know why you're changing them.

## Deploying a config change
1. Edit `rate-limiter.config.yaml` (keep `max_tokens` in 50–200 unless there is a written reason).
2. Ship it as a **config deploy** (gets a `dep-####` id in `deployments.yaml`). Config-only deploys
   carry no code diff, so they are easy to overlook in a change review — see `deploy-rollback.md`.
3. Watch `ratelimit_rejected_total` **and** `redis_connected_clients` for ~10 minutes after rollout.

## Rolling back
Revert `rate-limiter.config.yaml` to the previous values and redeploy, or roll back the offending
`dep-####` (see `deploy-rollback.md`). Confirm `redis_connected_clients` settles back under the cap
and checkout latency/5xx return to baseline.

## Escalation
team-platform (priya → sam → mei). If checkout is impacted, coordinate with team-payments (raj).
