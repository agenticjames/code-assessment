# Runbook — checkout on-call

**Service:** `checkout` (core tier) · **Owner:** team-payments (on-call: raj; escalation: mei)
**SLO:** p99 < 800ms (`checkout-latency`) · **Related:** `runbooks/redis-connection-pool.md`,
`runbooks/rate-limiter-operations.md`, `runbooks/deploy-rollback.md`

## What checkout is
The revenue-critical path: it places customer orders. Checkout **acquires a Redis connection per
request**, so it is sensitive to the health of the shared Redis pool. Checkout failures map roughly
1:1 to lost orders (~$4.2k/min at peak — see `slos.yaml`), so treat customer-facing checkout
problems as high severity.

## Dependencies (what checkout calls)
`rate-limiter`, `auth-service`, `redis`, `orders-db`, `payment-gateway`, `inventory`.
A fault in **any** of these can surface as a checkout error or timeout, so localize before you act.

## SLO & alerts
- `checkout-p99-slo` — fires when rolling p99 > 800ms for 5m.
- `checkout-5xx-high` — fires when the 5xx rate exceeds 5% for 2m.
- `api-gateway` emits **504** when checkout times out upstream — a 504 spike on `POST /checkout` is
  the customer-visible signature.

## Common failure modes (and where to look)
1. **Connection-acquisition timeouts → check the shared Redis pool FIRST.**
   Symptom: checkout logs "timeout waiting for connection" and 504s climb. This *looks* like an
   `orders-db` problem but is **usually the shared Redis pool**, often driven by another tenant
   (rate-limiter / cart). Compare `redis_connected_clients` vs `maxclients`; see the Redis runbook.
   **Do not** assume the database until the pool is ruled out.
2. **payment-gateway flakiness.** A third-party processor (`payment-gateway`, `external: true`) can
   be intermittently slow/erroring; checkout surfaces this as payment failures or timeouts. Check
   payment-gateway health/latency before blaming checkout code.
3. **orders-db slow queries.** Genuine DB contention (slow queries, a heavy migration *still
   running*) raises checkout latency. Confirm with `orders-db` latency metrics — but note a
   *completed* migration with flat DB latency is **not** the cause (classic alibi).

## First moves
- Scope the time window; line up the 504 onset against recent **changes** (`deployments.yaml`) —
  including **config-only** deploys, which are easy to miss (see `deploy-rollback.md`).
- Pull `redis_connected_clients`, checkout p99/5xx, and the relevant upstream's health together so
  timing decides the cause rather than the keyword in the error text.

## Escalation
Primary: **team-payments → raj**. If it spans shared infra (Redis / rate-limiter), pull in
**team-platform (priya / sam)**. For SEV1 customer impact, escalate to the incident commander
**mei**. Prior related post-mortem: **INC-0987** (Redis connection starvation on the shared pool).
