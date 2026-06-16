---
# scenarios/E-deploy-regression/HIDDEN_TRUTH.md
# MACHINE-GRADEABLE ANSWER KEY — never fed to the agent. The eval harness + citation
# verifier score the agent's investigation against the fields below.
#
# WHAT E GRADES: this scenario is the INVERSE of Scenario C. The evidence is clean, single-
# service, and tightly time-correlated, and the rollback already CONFIRMED the cause. The
# correct behaviour is to be DECISIVE — a single root cause at HIGH confidence (>=0.9) with a
# concrete action. Manufacturing doubt or hedging here is the failure mode (the complement to
# C, where over-confidence is the failure mode).
scenario: E
slug: deploy-regression
outcome: root_cause                         # root_cause | inconclusive
root_cause:
  service: search
  change: dep-5b71
  mechanism: >
    Search deploy dep-5b71 (author theo) @08:15 removed the null/empty guard on the incoming
    `query` parameter in SearchHandler.parseQuery. Requests with a missing or empty query (a
    normal fraction of real traffic) now reach parsing logic that dereferences the null query,
    throwing a NullPointerException and returning HTTP 500. Search 500s climb immediately at
    08:16, one minute after the deploy.
  onset: 2026-06-16T08:16:00Z
  confirmed_by_fix: >
    dep-5b71 was rolled back @08:40 and the search error rate dropped straight back to baseline
    (~0.1%) within ~1 minute. A rollback that immediately resolves the symptom confirms the
    deploy as the cause.
herring:
  service: none
  note: >
    No herring is planted. Single service, no shared-infra twist, no competing change in the
    window. The one earlier deploy (dep-9c50, recommendations, 06:40) is unrelated, on a
    different service, and well before onset — it is an alibi-by-timing, not a real candidate.
noise_to_drop: []
required_citations:                         # telemetry/ paths; verifier substring-matches
  - "telemetry/deploys.yaml :: dep-5b71"
  - "telemetry/logs/search.log :: NullPointerException"
  - "telemetry/changes/dep-5b71.diff"       # the removed null/empty guard — the visible mechanism
expected_confidence:                        # graded as ranges
  search: ">=0.9"                           # HIGH CONFIDENCE IS CORRECT HERE — clean evidence + confirmed by rollback.
                                            # (Contrast C, where the correct top confidence is ~0.45-0.60.)
must:
  - "name a single confirmed root cause (dep-5b71) — do NOT hedge or present multiple live hypotheses"
memory_recall:
  - "INC-1108"                              # OPTIONAL/soft: prior 'checkout 504s after a bad deploy, fixed by rollback'
                                            # is the same class (deploy regression resolved by rollback). Nice-to-have
                                            # recall, not required for credit — E's signal is the in-window evidence.
expected_actions:
  - "roll back dep-5b71 (the rollback @08:40 already confirmed it resolves the incident)"
  - "follow up: restore the null/empty query guard and add a regression test before re-deploying"
---

# Causal chain (for human graders)

The root cause is **not stated in any single evidence file**, but the chain here is SHORT and
CLEAN by design — that is the point:

1. **Sharp onset right after a deploy.** `changes/deployments.yaml` shows `dep-5b71` (service:
   search, author: theo) deployed @08:15. `metrics/search_error_rate.csv` is flat ~0.1% until
   08:15, then STEPS to ~8% at 08:16 — a one-minute gap. `logs/search.log` shows clean 200s
   before 08:16, then repeated 500s from 08:16.

2. **A clear, named mechanism.** `logs/search.log` carries repeated `NullPointerException` stack
   traces at `SearchHandler.parseQuery`. `changes/dep-5b71.diff` shows the deploy **removed** the
   guard `if (query == null || query.isEmpty()) return emptyResults();` — so an empty/missing
   `query` now NPEs. The diff makes the cause visible, not inferred.

3. **The rollback confirms it.** `deployments.yaml` records dep-5b71 **rolled back @08:40**;
   `search_error_rate.csv` drops back to ~0.1% right after 08:40; `logs/search.log` returns to
   200s. A rollback that immediately fixes the symptom is direct confirmation.

4. **No competing cause.** Single service (search), no shared infra, no herring; the only other
   deploy (`dep-9c50`, recommendations @06:40) is on a different service and well before onset.

**Decisiveness is the graded behaviour.** Because the evidence is clean, single-service, and
**confirmed by the rollback**, the correct output is ONE root cause (dep-5b71) at HIGH confidence
(>=0.9) with a concrete action (roll back dep-5b71). This is the deliberate complement to
Scenario C: C must stay calibrated and unsure on genuinely ambiguous evidence; E must be
decisive and not manufacture doubt on clean evidence.
