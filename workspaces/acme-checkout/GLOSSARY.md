# Glossary — Acme Checkout

A small dictionary so the investigator (and a human reviewer) can read the world without guessing.

## Tiers
- **edge** — public entry (`api-gateway`, `cdn`).
- **core** — customer-facing business services (`checkout`, `cart`, `orders`, `search`, …).
- **platform** — shared internal services (`rate-limiter`, `auth-service`, `feature-flags`).
- **data** — stores and buses (`redis`, `orders-db`, `sessions-store`, `search-index`, `kafka`).
- **external** — third parties outside our control (`payment-gateway`, `shipping-api`, `email-provider`).

## Key terms
- **shared pool / connection pool** — the single set of **50** Redis connections shared by
  `rate-limiter`, `checkout`, and `cart` (see `adr/ADR-014-shared-redis.md`). Exhausting it
  starves all three; `checkout` is the highest-impact victim.
- **max_tokens** — the `rate-limiter` token-bucket size per client. Lower = more aggressive
  throttling **and** more bucket churn / more Redis connections held. Safe range ~50–200
  (see `runbooks/rate-limiter-operations.md`).
- **504 / gateway timeout** — `api-gateway` gave up waiting on an upstream (usually `checkout`).
- **OOMKilled** — a pod exceeded its memory limit and was killed.
- **war room** — the `#incidents` Slack channel where responders coordinate.

## Infrastructure (NOT product services — won't appear in topology)
- **log-aggregator** — central logging host. Chronically low on disk (a SEV4 that fires for
  days; see `INC-1003`). Not on any customer request path → typically noise during incidents.

## ID schemes (all times UTC)
`INC-####` incidents · `dep-####` deploys (4 hex) · `ZD-####` support tickets · alert
`fingerprint` = 8 hex.

## Cast (on-call engineers)
`raj` (payments) · `priya`, `sam` (platform / SRE) · `lena` (identity) · `dana` (data) ·
`theo` (growth) · `nina` (fulfillment) · `mei` (incident commander).
