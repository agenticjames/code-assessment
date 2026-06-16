---
id: INC-1120
title: Feature-flag misconfiguration briefly breaks checkout
date: 2026-06-03
severity: SEV2
services: [checkout, feature-flags]
duration: 17m
tags: [feature-flags, config, checkout, misconfig, rollout]
---

## Summary
Checkout broke for ~17 minutes after a **feature flag** was flipped to an invalid state. A flag
controlling a checkout code path was rolled out targeting the wrong audience / an unsupported value,
which sent checkout down a broken branch and errored the request. The fix was to **turn the flag
back off** — no deploy, no infrastructure involved.

## Timeline (UTC)
- 18:22  A feature-flag change for checkout is published via `feature-flags`.
- 18:25  Checkout errors climb for the affected users as the flag enables a broken/incomplete path.
- 18:30  Identified: the **flag configuration** is wrong (bad targeting / unsupported value), not a
         code deploy and not infra.
- 18:34  **Reverted the flag** to its previous (off) state.
- 18:39  Checkout errors clear immediately as traffic returns to the known-good path.

## Root cause
A **feature-flag misconfiguration** routed checkout requests into a code path that wasn't ready. The
mechanism was a **runtime flag value**, evaluated by `feature-flags` — entirely different from a
connection, capacity, deploy, or dependency failure. Toggling a flag, not exhausting a resource, is
what broke and then fixed checkout.

## Resolution / fix
- **Immediate:** reverted the flag to its prior state; checkout recovered at once.
- **Follow-up:** added validation on flag values + a staged rollout (small percentage first) so a
  bad flag is caught before it reaches all checkout traffic.

## Lessons learned
- When checkout breaks with **no deploy** in the change log, check **feature flags** — a flag flip is
  a change that doesn't appear as a `deploy`. The cause can be a config value, not connections or
  capacity.
- An **instant** recovery from toggling a flag confirms the **flag** as the cause; gate flag changes
  like any other risky rollout.
