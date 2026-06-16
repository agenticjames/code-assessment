# Runbook — Redis shared connection pool

**Service:** `redis` (data tier) · **Owner:** team-platform (on-call: priya; SRE: sam)
**Related:** `adr/ADR-014-shared-redis.md`, `runbooks/rate-limiter-operations.md`, `runbooks/checkout-oncall.md`

## What this pool is
There is **one** Redis instance with a **hard cap of 50 connections** (`max_connections: 50`).
Per ADR-014 it is **shared by three services**: `rate-limiter`, `checkout`, and `cart`. They
draw from the *same* 50-connection budget — this is a deliberate, cost-driven coupling, and it
is a classic **noisy-neighbor** setup. `checkout` is the highest-impact tenant because it is the
revenue path.

## How to read pool health
Two numbers tell the whole story:
- `redis_connected_clients` — connections currently held across **all** tenants.
- `redis_maxclients` (a.k.a. `maxclients`) — the ceiling (50).

Watch the **ratio**. The `redis-connections-saturated` alert fires at
`redis_connected_clients / redis_maxclients > 0.9`. When `connected_clients` reaches 50/50, Redis
**refuses new connections** and logs `max number of clients reached`. Confirm live with
`redis-cli INFO clients` (look at `connected_clients`) and `redis-cli CONFIG GET maxclients`.

## The symptom, and the trap
The on-call symptom is **"checkout connection-acquisition timeouts"** — checkout cannot obtain a
connection from the pool, requests stall, and `api-gateway` returns **504s**.

This is **commonly mistaken for a database problem**: the checkout error text mentions waiting for a
connection, so responders reach for `orders-db`. That is usually the wrong tree. When checkout shows
connection-acquisition timeouts, **suspect the shared Redis pool FIRST** — compare
`redis_connected_clients` to `maxclients`, then ask *what else* is holding connections right now.

## How one tenant starves the others (general mechanism)
A **misbehaving rate-limiter** is the usual culprit for sudden pool exhaustion. The rate-limiter
stores token buckets in this Redis. If it is misconfigured — buckets sized too small, so it churns
through far more bucket operations — or it simply opens too many clients, it can hold a
disproportionate share of the 50 connections and **starve checkout and cart**. (See the
rate-limiter runbook for the bucket mechanics and the safe `max_tokens` range.) In short, the
standing linkage in this stack is:

> **rate-limiter misconfig / churn → shared Redis pool exhaustion (50/50) → checkout can't acquire
> a connection → 504s.**

This is a property of the architecture, not a claim about any single incident; treat it as the
default hypothesis whenever the pool saturates.

## Remediation
1. **Relieve the ceiling** — raise `maxclients` to buy headroom (immediate, buys time, not a fix).
2. **Shed load** — drop non-critical traffic so checkout/cart can acquire connections.
3. **Fix the offending client** — identify which tenant is over-consuming and correct it (e.g.,
   revert a bad rate-limiter config; see `rate-limiter-operations.md` and `deploy-rollback.md`).
4. Verify recovery: `redis_connected_clients` falls back well under 50 and checkout 504s clear.

## Escalation
team-platform (priya, then sam). If checkout is customer-impacting, loop in team-payments (raj)
and the incident commander (mei). The long-term isolation fix (per-tenant connection budgets) is
tracked in **PLAT-2291** (unfunded).
