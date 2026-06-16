---
# scenarios/D-recurring/HIDDEN_TRUTH.md
# MACHINE-GRADEABLE ANSWER KEY — never fed to the agent. The eval harness + citation
# verifier score the agent's investigation against the fields below.
#
# THE WHOLE POINT OF D: this is the same FAILURE CLASS as INC-0987 (surge-driven
# exhaustion of the shared 50-connection redis pool), but every evidence file describes
# it in DIFFERENT WORDS ("connection errors", "couldn't get a connection", "connection
# refused", "pool maxed out") and DELIBERATELY AVOIDS INC-0987's phrasing ("ran out of
# available connections", "starvation"). So a keyword match against the library would
# MISS INC-0987; only a SEMANTIC (meaning-based) recall should surface it. D is graded
# primarily on whether the agent recalls and cites INC-0987 by meaning.
scenario: D
slug: recurring-connection-errors
outcome: root_cause                         # root_cause | inconclusive
root_cause:
  service: redis
  change: none                              # NO deploy/config change this time — the trigger is the traffic surge
  mechanism: >
    A marketing flash-promo email blast at 10:00 drove a traffic surge (~5x baseline) onto
    checkout and cart. Both draw redis connections per request from the SHARED 50-connection
    pool (shared by rate-limiter + checkout + cart per ADR-014). Under the surge, concurrent
    demand pushed the pool to 50/50 at ~10:02; redis began refusing new connections, so
    checkout and cart could not obtain a connection and orders started failing. Unlike INC-0987
    there is no misconfiguration — the surge alone was enough to max out the pool.
  onset: 2026-06-12T10:02:00Z
herring:
  service: none
  note: >
    No competing root cause is planted here. There is no deploy or config change in the
    window (changes/deployments.yaml shows a marketing_event, not a code change), so the
    only signal is the surge + the shared-pool exhaustion. D's difficulty is RECALL, not
    herring-rejection.
noise_to_drop: []
required_citations:                         # telemetry/ paths; verifier substring-matches
  - "telemetry/logs/redis.log :: max number of clients reached"   # also: 'Connection refused' lines climb under load
  - "telemetry/metrics/redis_connections.csv"                     # baseline ~20 -> pegged at 50 from 10:02
  - "telemetry/logs/checkout.log :: couldn't get a connection"    # connection errors from 10:01 (different words than INC-0987)
expected_confidence:                        # graded as ranges
  redis: ">=0.7"                            # shared-pool exhaustion under surge — target ~0.8
memory_recall:
  - "INC-0987"                              # THE GRADED SIGNAL: same class (surge-driven shared-pool exhaustion)
                                            # + same fix. Must be recalled by MEANING — the vocabulary here is
                                            # deliberately different from INC-0987's, so keyword search will not find it.
memory_recall_grading: >
  Full credit requires surfacing INC-0987 specifically and noting it is the SAME failure
  class (surge-driven exhaustion of the shared redis pool) with the SAME remediation. A
  STRONG match is expected (this is a true recurrence, not a near-miss). Near-miss library
  entries that share the "redis" keyword but a different cause (e.g. INC-1042 redis latency
  from an AZ partition) must NOT be treated as the match — surfacing them as the answer is a
  retrieval-discrimination failure.
expected_actions:
  - "apply the INC-0987 remediation: raise redis maxclients to buy headroom and/or shed non-critical load so checkout+cart can acquire connections"
  - "isolate the rate-limiter (and ideally per-tenant) connection budgets so a surge can't max out the shared pool — the deferred fix from INC-0987 (PLAT-2291)"
  - "for the immediate promo: throttle / stagger the blast or pre-scale the pool ahead of marketing surges"
---

# Causal chain (for human graders)

The root cause is **not stated in any single evidence file**. It is reconstructible by
chaining across files, and the *prior-incident match* is the graded capability:

1. **Connection errors at checkout/cart from ~10:01.** `logs/checkout.log`
   (`couldn't get a connection from the pool`, `connection refused by redis`) and
   `alerts/alerts.json` (a redis-saturation alert at 10:02, a checkout 5xx alert at 10:03,
   a cart error alert) establish a sharp-onset connection-failure incident.

2. **The shared pool is maxed.** `logs/redis.log` (`max number of clients reached (50/50)`,
   connection refusals climbing from ~10:01) and `metrics/redis_connections.csv` (baseline
   ~20, surges to 50 by 10:02, pegged) show the single 50-connection pool at its ceiling.

3. **No change to blame — a surge instead.** `changes/deployments.yaml` records **no deploy
   or config change** in the window; instead a `marketing_event` notes a flash-promo email
   blast at 10:00 with traffic ~5x baseline. So the trigger is **demand**, not a code change.
   (This is the key difference from Scenario A, where a rate-limiter misconfig drove the
   pool to 50/50.)

4. **Topology supplies the mechanism.** `topology/services.yaml` + `adr/ADR-014-shared-redis.md`:
   checkout, cart, and rate-limiter share ONE redis pool capped at 50. A surge onto
   checkout+cart can exhaust it on its own.

5. **The recall.** This is the **same failure class as INC-0987** — a traffic surge (there a
   flash sale, here a flash promo) driving the **shared redis pool to its connection ceiling**,
   causing checkout to fail orders. INC-0987's remediation (raise the ceiling, shed load,
   isolate the rate-limiter's budget — PLAT-2291) applies directly. The agent must surface
   INC-0987 **by meaning**: this scenario's evidence never uses INC-0987's phrases ("ran out of
   available connections", "starvation"), so a literal keyword match fails.

**Human hint (a nudge, not the answer):** in `chat/incident-war-room.md`, sam/priya note the
redis connections are pegged at 50 "again" and that it "feels like the Valentine's thing." A
good investigation surfaces **INC-0987 itself** (the Valentine's flash-sale post-mortem) from
the library and cites it, rather than relying on a teammate's vague memory.
