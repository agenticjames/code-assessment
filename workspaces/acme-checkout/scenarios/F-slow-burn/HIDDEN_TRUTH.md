---
# scenarios/F-slow-burn/HIDDEN_TRUTH.md
# MACHINE-GRADEABLE ANSWER KEY — never fed to the agent. The eval harness + citation
# verifier score the agent's investigation against the fields below.
#
# WHAT F GRADES: TREND reasoning + resisting a deploy-correlation that isn't there. The
# signal is a multi-day SLOPE (a gradual memory leak), not a point event. There is NO recent
# deploy to blame — the last deploy (dep-8c22) predates the trend and doesn't line up. The
# correct behaviour is to diagnose the gradual saturation from the trend and EXPLICITLY note
# that no recent deploy correlates. This is the opposite temporal mode from A/B/E (sharp onset).
scenario: F
slug: slow-burn
outcome: root_cause                         # root_cause | inconclusive
root_cause:
  service: checkout
  change: none                              # NO recent deploy correlates — the cause is a gradual trend, not an event
  mechanism: >
    A gradual memory leak in checkout: heap usage climbs steadily over ~5 days (06-11 ~42% ->
    06-16 ~86%), driving longer and more frequent garbage-collection pauses, which in turn push
    checkout p99 latency up over the period (~540ms -> ~760ms, approaching the 800ms SLO). The
    degradation is a slope, not a step — there is no single triggering event.
  onset: gradual                            # ~2026-06-11 onward; no sharp onset timestamp
key_behavior:
  - "identify the multi-day UPWARD trend (heap % and p99 both climbing 06-11 -> 06-16), not a point event"
  - "EXPLICITLY note that NO recent deploy correlates — the last deploy (dep-8c22) is 2026-06-09, before the trend, and does not line up; resist blaming it"
herring:
  service: none
  note: >
    No competing root cause is planted. The deliberate trap is the ABSENCE of a deploy: an
    investigator pattern-matching 'incident => find the deploy' will reach for dep-8c22 and be
    wrong (it predates the trend and the metrics don't move at its timestamp). The correct move
    is to notice the empty recent-deploy window and read the slope instead.
noise_to_drop: []
required_citations:                         # telemetry/ paths; verifier substring-matches
  - "telemetry/metrics/checkout_memory.csv" # the leak signature: ~42% -> ~86% over 5 days, dip on 06-14 (restart)
  - "telemetry/logs/checkout.log :: GC pause"  # GC pause WARNINGs whose duration/frequency escalate across days
expected_confidence:                        # graded as ranges
  checkout: "0.6..0.75"                     # a trend diagnosis — slightly less certain than E's clean case (>=0.9).
                                            # Should NOT be near-1.0 (no confirming event/fix), nor inconclusive.
memory_recall: []                           # no library entry is the intended match; recall is not graded for F
expected_actions:
  - "mitigate now: rolling restart of checkout pods to reclaim heap and shed the GC pressure (buys time, not a fix)"
  - "find the leak: capture a heap profile / dump on a hot pod and diff allocations to locate the leaking allocation"
expected_open_questions:
  - "which code path is leaking — not determinable from metrics/logs alone; needs a heap profile"
  - "what started the climb around 06-11 (a traffic-pattern change? a slow buildup?) is not pinned down by the available evidence"
---

# Causal chain (for human graders)

The root cause is **not stated in any single evidence file**, and crucially it is a TREND, so
it is read off slopes rather than a single onset moment:

1. **A multi-day upward trend, no sharp onset.** `metrics/checkout_memory_daily.csv` (6-hourly)
   climbs steadily from ~42% heap on 06-11 to ~86% on 06-16, with a visible **dip on 06-14**
   (a pod restart) before resuming the climb — a classic leak sawtooth.
   `metrics/checkout_p99_daily.csv` creeps from ~540ms to ~760ms over the same window,
   approaching the 800ms SLO. Two correlated slopes, not a step change.

2. **The mechanism is in the logs.** `logs/checkout.log` carries `GC pause` WARNING lines whose
   duration and frequency **escalate across days** — occasional ~120ms pauses on 06-11 growing
   to frequent ~900ms pauses by 06-16 — with a brief improvement after the 06-14 pod restart
   that then regresses. Rising heap -> longer/more GC pauses -> higher p99.

3. **No deploy correlates (the deliberate trap).** `changes/deployments.yaml` shows the recent
   window is **empty**: the last checkout deploy is `dep-8c22` on **2026-06-09**, two days before
   the trend begins, and the metrics do not move at that timestamp. An investigator that reflexively
   blames "the latest deploy" is wrong here. The correct reasoning explicitly states that **no
   recent deploy lines up**, so this is gradual resource saturation, not a release regression.

**Graded behaviours:** (a) diagnose the gradual memory leak / saturation from the **trend**;
(b) **explicitly note that no recent deploy correlates** (resist deploy-blame); (c) recommend the
right remediation — a **rolling restart to mitigate** plus **heap profiling to locate the leak**.
Confidence ~0.65-0.75: well-supported by the trend, but without a confirming event/fix it is
appropriately below E's clean >=0.9. This is the inverse temporal mode of A/B/E.
