---
# scenarios/G-range-retro/HIDDEN_TRUTH.md
# MACHINE-GRADEABLE ANSWER KEY — never fed to the agent.
#
# WHAT G GRADES: open-ended RANGE reasoning over the continuous corpus. The query names a
# date range, not an incident. The correct output is a TIMELINE of the distinct events in that
# range (two of them), each with its own cause — NOT a single root cause, and NOT anything from
# outside the range. This is only answerable because telemetry is one time-indexed history.
scenario: G
slug: range-retro
outcome: multi_incident
query_range: ["2026-06-10", "2026-06-12"]

events:                                       # the agent should surface BOTH, as a timeline
  - date: 2026-06-10
    incident: B (auth-service OOM cascade)
    summary: >
      ~21:05 dep-3a8c cut auth-service memory 2Gi->1Gi; auth OOMed/crashlooped from ~21:10, and
      because nearly every core service calls auth, checkout (and ~18 others) threw 401s / auth
      timeouts. Reverted 21:28.
    citations: ["telemetry/deploys.yaml :: dep-3a8c", "telemetry/logs/auth-service.log :: OOMKilled"]
  - date: 2026-06-12
    incident: D (shared redis pool exhaustion under a promo surge)
    summary: >
      A 10:00 flash-promo surge (~5x) drove the SHARED 50-connection redis pool to 50/50 by 10:02;
      checkout couldn't acquire connections and failed orders. Shed load + raised maxclients ~10:40.
      Same class as INC-0987.
    citations: ["telemetry/logs/redis.log :: max number of clients reached", "telemetry/metrics/redis_connections.csv"]

must:
  - "scope telemetry to the [2026-06-10, 2026-06-12] range"
  - "return a TIMELINE of the TWO distinct incidents (06-10 auth, 06-12 redis), each with its own cause"
must_not:
  - "conflate the two into a single root cause — they are unrelated"
  - "pull in OUT-OF-RANGE events: the 06-16 checkout 504s (A), the 06-16 search regression (E), or the F slow-burn trend"
noise_to_drop:
  - "the chronic disk-space SEV4 (log-aggregator) fires daily inside the range too — still noise"
expected_confidence: "high on each event individually (both are clean, already-resolved incidents)"
expected_actions:
  - "summarize the two events as a brief timeline; note both are resolved; flag the shared-pool risk (ADR-014/PLAT-2291) as recurring"
---

# Why this scenario exists (for human graders)

A range query is the capability the continuous corpus unlocks — it is *impossible* against
per-incident folders. "Between the 10th and the 12th" must be answered by slicing the shared
`telemetry/` to that window and reading out whatever happened, which here is **two unrelated
incidents**:

- **2026-06-10 — auth OOM cascade (B):** a memory-limit cut OOMed auth-service; checkout was a
  downstream victim (401s / auth timeouts), not the origin.
- **2026-06-12 — redis pool exhaustion (D):** a promo surge maxed the shared 50-connection pool;
  checkout couldn't get a connection.

The graded behaviours: (a) correctly **scope to the range** (the prominent 06-16 checkout 504s
and the week-long slow-burn are OUT of range and must not appear); (b) report a **timeline of two
distinct causes**, not one; (c) recognize that on both days checkout's instability was driven by a
*dependency* (auth on the 10th, the shared redis pool on the 12th), which is the throughline worth
calling out. Collapsing both into a single root cause, or dragging in out-of-range incidents, is the
failure mode.
