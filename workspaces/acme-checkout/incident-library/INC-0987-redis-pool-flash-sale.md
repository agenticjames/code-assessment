---
id: INC-0987
title: Checkout failures during flash sale — Redis connection starvation
date: 2026-02-14
severity: SEV1
services: [checkout, redis, rate-limiter]
duration: 38m
tags: [redis, connections, capacity, flash-sale, noisy-neighbor, shared-pool]
---

## Summary
During the Valentine's flash sale, a traffic surge drove the shared Redis instance to
**run out of available connections**. Checkout could not obtain a connection from the
pool and began failing customer orders. The root cause was connection **starvation** on
the shared pool — not a Redis fault, and not a code bug.

## Timeline (UTC)
- 11:00  Flash sale begins; traffic ~6x baseline.
- 11:06  Checkout order-placement errors climb; customers report "something went wrong."
- 11:09  Redis client count reaches the ceiling; new connection attempts are refused.
- 11:18  Identified: the shared pool is saturated — rate-limiter, checkout, and cart are
         all contending for the same 50 connections.
- 11:30  Mitigated: raised the connection ceiling and shed non-critical load.
- 11:38  Recovered.

## Root cause
The shared Redis pool (see ADR-014) has a hard ceiling of 50 connections. Under the
surge, concurrent demand from checkout and the rate-limiter exceeded it, leaving checkout
**starved of connections**. The other services were victims, not causes.

## Resolution / fix
- **Immediate:** raised `maxclients` and shed non-critical traffic.
- **Follow-up:** **isolate the rate-limiter onto its own connection budget** so it can no
  longer crowd out checkout (partial; tracked in PLAT-2291).

## Lessons learned
- `redis_connected_clients` vs `maxclients` is the leading indicator — watch it.
- The shared pool is the **first** thing to check when checkout shows connection-acquisition
  problems. The symptoms often *look like* a downstream database issue, which sends
  responders the wrong way.
