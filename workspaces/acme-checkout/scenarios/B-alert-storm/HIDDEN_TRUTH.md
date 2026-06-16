---
# scenarios/B-alert-storm/HIDDEN_TRUTH.md
# MACHINE-GRADEABLE ANSWER KEY — never fed to the agent. The eval harness + citation
# verifier score the agent's investigation against the fields below.
scenario: B
slug: alert-storm
outcome: root_cause                          # root_cause | inconclusive
root_cause:
  service: auth-service
  change: dep-3a8c
  mechanism: >
    auth-service config change dep-3a8c @21:05 lowered the pod memory limit 2Gi->1Gi.
    auth-service's normal working set is ~1.5Gi, so under normal traffic the pods crossed
    the 1Gi (1024Mi) limit (~21:08) and the kernel began OOMKilling them (~21:10), driving a
    crashloop (CrashLoopBackOff). While auth-service was restarting, token validation failed
    or timed out. Because auth-service is on the request path of nearly every core service
    (high fan-in), EVERY dependent began throwing 401s / "auth check timed out" / elevated
    latency at once. The ~18 downstream alerts are a cascade from this single origin, not
    independent faults.
  onset: 2026-06-10T21:10:00Z              # first OOMKill; mem crossed 1Gi at ~21:08
symptoms:                                   # downstream alerts that are EFFECTS, not causes
  description: >
    All of the following alerting services depend_on auth-service in topology/services.yaml
    and fire only because auth is unavailable. They will clear on their own once auth recovers.
  services:
    - checkout          # checkout-5xx-high, checkout-p99-slo, CheckoutAuthTimeout
    - cart              # CartLatencyHigh, CartFivexxHigh, CartAuthTimeout
    - orders            # orders-5xx-high, OrdersLatencyHigh, OrdersAuthTimeout
    - search            # search-5xx-high, SearchLatencyHigh
    - recommendations   # RecommendationsLatencyHigh, RecommendationsFivexxHigh
    - user-profile      # UserProfileLatencyHigh, UserProfileFivexxHigh
    - notifications     # NotificationsLatencyHigh, NotificationsFivexxHigh
    - api-gateway       # GatewayFivexxHigh — second-order: aggregates the failing core services
noise_to_drop:
  - "Alert ORDERING is a trap: the auth-service alerts (AuthErrorRateHigh @21:13, AuthPodOOM @21:14) are NOT the earliest. Four downstream alerts (cart/checkout @21:11, orders/user-profile @21:12) fired BEFORE the first auth alert due to detection lag. 'First to alert' points at cart/checkout (wrong)."
  - "Alert VOLUME is a trap: auth-service has only 2 alerts; the downstream services collectively have ~18. 'Most alerts' points at the downstream noise (wrong). Only grouping by shared upstream dependency finds auth."
  - "dep-2d71 (search deploy @18:32) — distractor: ~3h before onset, recovered clean; theo briefly chases it. Timing alibi."
  - "dep-6b04 (notifications deploy @20:11) — distractor: cosmetic email-template change, no shared-infra impact."
herring:
  service: orders-db
  why_plausible: >
    orders and user-profile throw 5xx and team-data is paged, so a database fault looks
    possible; dana is initially suspected of it.
  disconfirm:
    - "orders.log shows orders-db SELECT 1 at 3-4ms and pool 14/100 throughout — db healthy"
    - "the orders/checkout errors are explicitly 'auth check timed out' / '401 from auth-service', naming the auth upstream, not the db"
    - "no db deploy/migration in the window; the only auth-path change is dep-3a8c"
required_citations:                         # telemetry/ paths; verifier substring-matches
  - "telemetry/deploys.yaml :: dep-3a8c"
  - "telemetry/logs/auth-service.log :: OOMKilled"
  - "telemetry/deploys.yaml :: memory limit 2Gi -> 1Gi"
  - "telemetry/metrics/auth_memory.csv :: crosses 1024Mi at ~21:08 then sawtooths against the cap"
expected_confidence:                        # graded as ranges
  auth-service: ">=0.75"                    # target ~0.85
  orders-db: "<=0.1"
expected_open_questions:
  - "dep-3a8c shipped straight to prod with no canary/soak (changes/deployments.yaml canary: none) — a canary would likely have OOMed first and caught it"
  - "exact per-pod working-set headroom not captured (memory sawtooths against the 1024 cap, so the true ~1.5Gi footprint is only visible after the revert restores 2Gi)"
memory_recall:
  - "INC-1095"                              # prior auth-service OOM after a memory-limit change — same class, same fix
expected_actions:
  - "revert dep-3a8c / restore the auth-service memory limit to 2Gi (done @21:28 as dep-3a8c-revert) — the downstream alerts clear on their own as auth recovers"
  - "do NOT triage the ~18 downstream services individually; they are symptoms of the one upstream"
  - "ship the INC-1095 follow-up guardrail: block memory-limit reductions below measured working set + headroom; page OOMKilled to the owning team"
---

# Why it's auth (the fan-in argument, for human graders)

The root cause is **not stated in any single evidence file**. The storm collapses to one
service only by reasoning over the dependency graph:

**The fan-in.** In `topology/services.yaml`, every service that alerted —
`checkout`, `cart`, `orders`, `search`, `recommendations`, `user-profile`, `notifications` —
has `auth-service` in its `depends_on` (and `api-gateway` sits above all of them). `auth-service`
is the **single shared upstream** of the entire storm. When ~20 alerts fan in to one common
dependency, that dependency is the lead — not the loudest service and not the first to page.

**The two heuristics that MISLEAD here (by design):**
1. *"What alerted first?"* → `cart` and `checkout` at **21:11**. But auth's own alerts
   (`AuthErrorRateHigh` 21:13, `AuthPodOOM` 21:14) fire **after** four downstream alerts —
   detection lag on the OOM/crashloop signal. First-to-alert points at the wrong service.
2. *"What has the most alerts?"* → the downstream services have ~18 between them; `auth-service`
   has just 2. Volume points at the symptoms.

Only **grouping the alerts by their shared upstream dependency** isolates `auth-service`.

**The mechanism, corroborated in multiple vocabularies:**
- `changes/deployments.yaml`: `dep-3a8c` @21:05 lowered the auth-service pod memory limit
  **2Gi → 1Gi** (manifest diff shows `limits.memory 2Gi → 1Gi`).
- `runbooks/auth-service.md`: normal working set is **~1.5Gi**; the limit **should be 2Gi**;
  reducing it guarantees OOM under normal load.
- `metrics/auth_memory.csv`: usage crosses **1024Mi at ~21:08**, then **sawtooths** against the
  cap (climb → ~1030 → OOMKill → drop to ~300 on restart → climb), and only settles at ~1500
  **after** the 21:28 revert restores 2Gi.
- `logs/auth-service.log`: `OOMKilled` (`reason=OOMKilled exit_code=137`) repeatedly →
  `CrashLoopBackOff`; occasional successful validations between restarts.
- `logs/checkout.log` + `logs/orders.log`: the downstream errors are explicitly
  `auth check timed out` / `401 from auth-service`, with the dependents' own backends
  (redis, orders-db, kafka, payment-gateway) reported **healthy** — proving they are victims.

**Memory:** this is the same failure *class* as **INC-1095** (auth-service OOM after a
memory-limit change), with the same fix (restore the limit; never trim below the working set).

**Human-trust note:** in `chat/incident-war-room.md` the responders are overwhelmed
("is everything down?!"), `theo` briefly chases the unrelated `search` deploy `dep-2d71`,
and `dana` is suspected for orders-db. The turn comes when `lena` observes that *every* alerting
service calls auth-service and groups the storm by that shared dependency — then finds her own
`dep-3a8c` as the cause. A good investigation reaches the same fan-in conclusion from the
evidence without being led by the (initially misdirected) chat.
