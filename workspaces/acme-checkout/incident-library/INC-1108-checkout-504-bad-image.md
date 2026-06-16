---
id: INC-1108
title: Checkout 504s after a bad container image rollout
date: 2026-05-19
severity: SEV2
services: [checkout, api-gateway]
duration: 23m
tags: [checkout, deploy, container-image, rollback, regression]
---

## Summary
`api-gateway` returned **504s on POST /checkout** for ~23 minutes. The trigger was a **bad container
image**: a checkout deploy shipped an image with a broken startup path, so the new pods came up
unhealthy and timed out requests. This was a **deploy regression**, fixed by **rolling back to the
previous image** — nothing to do with Redis, connections, or the rate-limiter.

## Timeline (UTC)
- 16:02  Checkout deploy `dep-3c19` rolls out a new container image.
- 16:05  New checkout pods fail readiness; healthy pods drain as the rollout proceeds.
- 16:07  api-gateway 504s on `POST /checkout` climb as healthy capacity drops.
- 16:14  Identified: the rolled-out **image** is broken (bad build artifact), not infra.
- 16:18  **Rolled back** to the prior image (`dep-3c19` reverted); new pods go healthy.
- 16:25  504s clear; checkout latency back to baseline.

## Root cause
The deployed **container image** was defective — a packaging/startup regression that made checkout
pods fail health checks. The 504s were the gateway timing out on unhealthy upstream pods. Redis,
the shared pool, and rate-limiter config were all **uninvolved** and healthy throughout; this was
purely a **bad-build deploy regression**.

## Resolution / fix
- **Immediate:** rolled back checkout to the last known-good image; confirmed pods healthy.
- **Follow-up:** added an image smoke-test gate in CI and a canary step so a broken image fails
  before a full rollout.

## Lessons learned
- "Checkout 504s" is a **symptom with multiple causes.** Two very different ones: a **bad deploy /
  image** (this incident — check `deployments.yaml` for a recent checkout image deploy) vs. shared
  **Redis pool** contention (a different class — check connection counts). The discriminator is
  *what changed* and *whether pods are healthy*, not the 504 itself.
- A clean rollback that **immediately** fixes the symptom points at the **deploy** as the cause.
