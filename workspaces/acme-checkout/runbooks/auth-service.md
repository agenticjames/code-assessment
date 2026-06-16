# Runbook — auth-service

**Service:** `auth-service` (platform tier) · **Owner:** team-identity (on-call: lena; escalation: mei)
**SLO:** 99.95% successful token validations (`auth-availability`) · **Depends on:** `sessions-store`
**Related:** `runbooks/deploy-rollback.md`

## Why auth-service is special: high fan-in
auth-service validates tokens / sessions on the request path of **nearly every core service** — it
sits upstream of roughly **8 services** (checkout, cart, orders, search, recommendations,
user-profile, notifications, and more). Because so much depends on it, **a degradation here cascades
widely**: when auth-service struggles, every service that checks a token starts throwing
401s/timeouts at once. In an alert storm, this is the **one upstream** that explains many downstream
alerts — group alerts by their shared dependency on auth before chasing individual services.

## Memory sizing
- **Normal working set: ~1.5Gi.**
- **Memory limit should be 2Gi** — about 0.5Gi of headroom over the normal footprint.

That headroom is not slack to reclaim. **Reducing the memory limit is dangerous**: with the limit at
or near the working set, normal traffic pushes the pod over its limit and the kernel OOM-kills it.

## OOM symptoms
- Pods **OOMKilled** (`auth-pod-oom` alert: `reason=OOMKilled`), often repeatedly.
- **Crashloop** — the pod restarts, warms up, hits the limit again, dies again.
- **Downstream auth-validation failures** — dependents report 401s / "auth check timed out" while
  auth-service is restarting. The blast radius looks huge even though the origin is a single service.

## Remediation
- **Restore the memory limit to 2Gi** (or revert the change that lowered it). This is the fix when
  an OOM/crashloop follows a memory-limit reduction — see `deploy-rollback.md` to find and roll back
  the offending change (config-only changes are easy to overlook).
- Confirm recovery: pods stop OOMKilling, the crashloop ends, and downstream 401/timeout alerts
  clear on their own as auth-service stabilizes.
- If the working set has genuinely grown, size the limit **up** from 2Gi rather than trimming it.

## Escalation
Primary: **team-identity → lena**. Because the blast radius is wide, escalate early to the incident
commander **mei**. Prior related post-mortem: **INC-1095** (auth-service OOM after a memory-limit
change).
