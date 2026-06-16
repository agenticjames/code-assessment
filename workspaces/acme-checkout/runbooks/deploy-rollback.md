# Runbook — deploy & rollback

**Owner:** team-platform (release tooling; on-call: priya / sam), but **any** team rolls back its
own service. **Change log:** `deployments.yaml` (per scenario: `scenarios/*/changes/deployments.yaml`).
**Related:** `runbooks/rate-limiter-operations.md`, `runbooks/auth-service.md`

## The change log
Every deploy, config change, and migration is recorded in `deployments.yaml` as an event with:
`id` (a `dep-####`, 4 hex — e.g. `dep-7e2a`), `service`, `type` (`deploy` | `config` | `migration`),
`ts` (UTC), `author`, `status`, and a pointer to the diff. This is the **first artifact** to consult
when something breaks: line up the incident onset against what changed in the window.

## Finding a deploy by id
1. Open the window's `changes/deployments.yaml`.
2. Find the entry whose `id` matches the `dep-####` (or filter by `service` / `ts`).
3. Follow its diff pointer (e.g. a `*.config.diff` for config changes, or the commit) to see the
   actual change. Note the `status` — a `failed` or `rolled-back` entry is meaningful evidence
   (a *failed rollback* that didn't fix the symptom is an alibi for the thing rolled back).

## Rolling back
- **Code deploy:** redeploy the previous known-good build / revert the commit, then redeploy.
- **Config change:** revert the file to its prior values and redeploy (e.g. restore
  `rate-limiter.config.yaml`; see the rate-limiter runbook).
- **Migration:** migrations are **not** trivially "rolled back" — coordinate with the owning team
  (team-data for `orders-db`) before any down-migration.
- Record the rollback as its own entry in `deployments.yaml`, and **verify the symptom actually
  clears** — a rollback that doesn't change the symptom means you rolled back the wrong thing.

## Watch out: config-only deploys are easy to overlook
A **config-only** change (no code diff) — the canonical example is a `rate-limiter` config tweak —
is the easiest change to miss in a review, precisely because there's no code to read and it may look
innocuous. When triaging, **scan for `type: config` entries, not just code deploys.** Many "we
didn't deploy anything" incidents turn out to be a config change that nobody counted as a deploy.

## Escalation
The owning team rolls back its own service (see `teams.yaml`). For cross-service or customer-facing
impact, involve the incident commander **mei**.
