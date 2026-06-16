# ADR-014: Share one Redis instance across rate-limiter, checkout, and cart

- **Status:** Accepted
- **Date:** 2025-09-30
- **Deciders:** team-platform, team-payments
- **Tracking:** PLAT-2291 (isolation follow-up, unfunded)

## Context
We previously ran three small Redis instances — one for the rate-limiter token store,
one for checkout's idempotency/session cache, one for cart state. Utilization was low
(<15%) on all three. The Q3 cost review flagged the triple spend.

## Decision
Consolidate onto **one Redis instance** (`redis`, `max_connections: 50`) shared by
`rate-limiter`, `checkout`, and `cart`. Saves ~2/3 of the cache spend.

## Consequences
- **Positive:** lower cost; one instance to operate and patch.
- **Negative / accepted risk — noisy neighbor.** The three services share **one
  connection pool of 50**. A connection spike in any one of them — a misconfigured
  rate-limiter opening many buckets, or a traffic surge — can **starve the others** of
  connections. `checkout` is the highest-impact victim because it is the revenue path.
- **Mitigation (deferred):** per-client connection caps / separate pools were proposed
  but not funded. Tracked in PLAT-2291.

## Operational note
If `checkout` shows connection-acquisition timeouts, **suspect the shared pool first**:
compare `redis_connected_clients` against `maxclients`, and check what *else* is using
the pool right then. The symptom often *looks like* a downstream database problem even
though the real contention is in Redis. See `runbooks/redis-connection-pool.md`.

> This coupling is intentional and cost-driven, not accidental — and it is the most
> likely cause of cross-service connection contention in this stack.
