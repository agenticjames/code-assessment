---
# scenarios/A-checkout-504/HIDDEN_TRUTH.md
# MACHINE-GRADEABLE ANSWER KEY — never fed to the agent. The eval harness + citation
# verifier score the agent's investigation against the fields below.
scenario: A
slug: checkout-504
outcome: root_cause                         # root_cause | inconclusive
root_cause:
  service: rate-limiter
  change: dep-7e2a
  mechanism: >
    rate-limiter config deploy dep-7e2a @14:45 changed max_tokens 100->10. The much
    smaller buckets caused the rate-limiter to churn and hold far more connections on the
    SHARED redis pool (max 50, shared by rate-limiter + checkout + cart per ADR-014). The
    pool reached 50/50 at ~14:47, starving checkout of redis connections; checkout request
    handlers blocked acquiring a connection and timed out, so api-gateway returned 504s.
  onset: 2026-06-16T14:47:00Z
herring:
  service: orders-db
  why_plausible: >
    checkout's connection-acquisition timeouts do not name a pool, so they read like a DB
    problem; orders-db is checkout's direct dependency and a migration ran in-window.
  disconfirm:
    - "orders-db migration mig-0616 completed CLEAN at 14:12 — 35 min before onset (14:47)"
    - "dana rolled the migration back; rollback COMPLETED 14:58 and 504s CONTINUED (raj still seeing them 15:09)"
    - "orders_db_latency flat ~25ms through the 14:47-15:30 incident (only a small bump 14:00-14:12 during the migration, fully recovered)"
    - "trace checkout-req-trace: orders-db.query span is fast/healthy (~22ms); the budget burns on redis.acquire_connection (5000ms timeout)"
noise_to_drop:
  - "disk-space-low SEV4 on host log-aggregator — chronic, firing since 2026-06-13 (3 days), tied to INC-1003, never customer-impacting and off every request path"
required_citations:                         # telemetry/ paths; verifier substring-matches
  - "telemetry/changes/dep-7e2a.diff :: - max_tokens: 100 / + max_tokens: 10"
  - "telemetry/logs/redis.log :: max number of clients reached"
  - "telemetry/deploys.yaml :: dep-7e2a"
  - "telemetry/captures/2026-06-16T1450Z-redis-cli-info.txt :: connected_clients:50 / maxclients:50"
expected_confidence:                        # graded as ranges
  rate-limiter: ">=0.7"
  orders-db: "<=0.1"
expected_open_questions:
  - "no canary/staging metrics were captured for dep-7e2a — the change went straight to prod (kubectl shows no canary pod)"
  - "was cart also impacted? it shares the same redis pool (ADR-014) but no cart alert fired — undetected vs unaffected is unconfirmed"
memory_recall:
  - "INC-0987"                              # Redis connection starvation, same class + same fix (isolate rate-limiter pool, PLAT-2291)
expected_actions:
  - "roll back / revert dep-7e2a (restore max_tokens to a safe value ~100; safe range 50-200 per rate-limiter-operations runbook)"
  - "correct the status-page draft — it wrongly blames the database migration"
  - "expedite PLAT-2291 (per-client redis connection budget so rate-limiter cannot crowd out checkout)"
---

# Causal chain (for human graders)

The root cause is **not stated in any single evidence file**. It is reconstructible only
by chaining seven hops across files:

1. **504s, ~14:47.** `alerts/alerts.json` (checkout-5xx-high, checkout-p99-slo),
   `logs/api-gateway.log` (504 status=504 upstream=checkout), and `metrics/checkout_p99.csv`
   (600ms → 8200ms at 14:47) establish a sharp-onset checkout outage at the edge.

2. **Ambiguous symptom (the trap).** `logs/checkout.log` shows
   `timeout acquiring connection from pool after 5000ms` — it never says *which* pool.
   It reads like an `orders-db` problem, and a migration is mentioned in the same log.

3. **Topology disambiguates the pool.** `topology/services.yaml` + `adr/ADR-014-shared-redis.md`:
   checkout, cart, and rate-limiter share ONE redis pool capped at 50. So a connection
   problem at checkout can be caused by a *sibling* on the shared pool, not by the DB.

4. **Two changes in the window.** `changes/deployments.yaml`: an orders-db migration
   `mig-0616` (started 14:00) and a rate-limiter config deploy `dep-7e2a` (14:45).

5. **Timing discriminates.** The migration COMPLETED 14:12 — 35 minutes before onset, and
   its rollback at 14:58 did NOT fix the 504s (alibi). `dep-7e2a` landed 14:45; onset 14:47
   — a 2-minute gap. The trace makes the discriminator visible: the failing request burns
   its budget on `redis.acquire_connection` (~5000ms), while `orders-db.query` is fast.

6. **Mechanism.** `changes/rate-limiter.config.diff`: `max_tokens 100 → 10`. Per
   `runbooks/rate-limiter-operations.md` (safe range ~50–200) and the GLOSSARY, lower
   max_tokens = more bucket churn = more redis connections held by the rate-limiter.

7. **Confirmation in four vocabularies.** `logs/redis.log`
   (`max number of clients reached (50/50)`), `metrics/redis_connections.csv` (pegged at 50
   from 14:47), `tool-outputs/redis-cli-info.txt` (`connected_clients:50`, `maxclients:50`,
   `rejected_connections` nonzero), and `logs/rate-limiter.log` (loaded max_tokens=10,
   opening/churning many connections) all say the same thing in different words.

**Memory:** this is the same failure *class* as **INC-0987** (Redis connection starvation;
rate-limiter crowding checkout off the shared pool), and the same deferred fix (PLAT-2291).

**Human-consensus trap:** in `chat/incident-war-room.md`, `dana` confidently blames the
migration and rolls it back; `priya` notes the latency lines up with the rate-limiter deploy
and **gets talked over**. The `comms/status-page-draft.md` written ~15:00 wrongly blames the
database migration. A good investigation rejects the consensus and corrects the draft.
