---
id: INC-1095
title: auth-service OOM and crashloop after a memory-limit change
date: 2026-05-22
severity: SEV1
services: [auth-service, checkout, orders, search]
duration: 52m
tags: [auth, oom, memory, crashloop, cascade, config]
---

## Summary
**auth-service pods kept getting killed** and crashlooping for nearly an hour. A config change had
**lowered the pod memory limit** below what auth-service actually needs, so under normal traffic the
pods **ran out of memory** and were OOMKilled. Because almost every service checks tokens through
auth, **every service that checks tokens started failing** — the blast radius looked enormous, but
there was a single origin.

## Timeline (UTC)
- 13:40  A platform config change reduces the auth-service memory limit.
- 13:48  auth-service pods begin getting **OOMKilled**; they restart and die again (crashloop).
- 13:51  Downstream 401s / "auth check timed out" surface across checkout, orders, search, and more.
- 14:05  Identified: auth pods are **out of memory** — the limit was set below the working set.
- 14:18  **Restored the memory limit**; pods stop dying and stabilize.
- 14:32  Downstream auth failures clear on their own as auth-service recovers.

## Root cause
The memory limit was lowered to roughly the normal working set, leaving no headroom. Normal traffic
pushed the pods past the limit and the kernel **OOM-killed** them repeatedly. The cascade of
downstream failures was a **symptom** of auth-service being unavailable, not independent faults in
those services — auth-service's high fan-in turned one bad limit into a fleet-wide auth outage.

## Resolution / fix
- **Immediate:** restored the auth-service memory limit to its previous (adequate) value; the
  crashloop ended.
- **Follow-up:** guardrail to block memory-limit reductions that drop below measured usage + the
  required headroom; alerting on OOMKilled tied directly to the owning team.

## Lessons learned
- When **many** services fail auth at once, look for **one** shared upstream — auth-service — rather
  than triaging each dependent. Grouping by the shared dependency collapses the storm.
- A memory limit set too close to the working set guarantees OOM under normal load. Keep headroom;
  if usage grew, size the limit **up**, never trim it to "save" memory.
