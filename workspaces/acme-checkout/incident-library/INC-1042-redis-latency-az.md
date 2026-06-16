---
id: INC-1042
title: Redis latency spike from an availability-zone network partition
date: 2026-04-08
severity: SEV2
services: [redis, cart]
duration: 41m
tags: [redis, network, latency, availability-zone, infrastructure]
---

## Summary
Redis command latency jumped sharply for ~40 minutes. The cause was **not** the Redis service
itself and **not** capacity — a **network partition between availability zones** put extra hops and
packet loss between clients in `us-east-1b` and the Redis primary in `us-east-1a`. Round-trips got
slow; the pool had **plenty of free connections** the whole time.

## Timeline (UTC)
- 09:14  Cart and other Redis callers see elevated p99 on Redis operations.
- 09:17  `redis_command_latency` climbs; **connection count stays normal/low** (no saturation).
- 09:25  Cross-AZ packet loss confirmed between `us-east-1b` and `us-east-1a` (cloud network event).
- 09:31  Traffic shifted to keep Redis clients in-zone with the primary; latency begins to fall.
- 09:55  Network path recovers; Redis latency back to baseline.

## Root cause
A provider-side **AZ network partition** degraded the path between Redis clients and the primary.
Latency was a **transport** problem (cross-zone hops + loss), not connection pressure: at no point
was the pool near its limit. This is explicitly a *different failure* from connection exhaustion —
the connections were healthy and available; the packets were slow.

## Resolution / fix
- **Immediate:** routed Redis traffic to stay within the primary's AZ to avoid the bad path.
- **Follow-up:** added a cross-AZ latency monitor distinct from the connection-saturation alert, so
  a *network* Redis problem is not confused with a *capacity* one.

## Lessons learned
- "Redis is slow" has at least two unrelated causes: **network latency** (this incident) vs.
  **connection saturation** (a different class entirely). Check `redis_command_latency` **and**
  `redis_connected_clients` — they point at different root causes.
- Normal connection counts during a Redis latency event are a strong signal the problem is the
  **network**, not the pool.
