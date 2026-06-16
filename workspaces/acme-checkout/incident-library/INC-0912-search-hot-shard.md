---
id: INC-0912
title: Slow search from an Elasticsearch hot shard
date: 2025-12-30
severity: SEV3
services: [search, search-index]
duration: 58m
tags: [search, elasticsearch, hot-shard, latency, data-skew]
---

## Summary
Product **search** was slow for nearly an hour. One Elasticsearch **shard** on the `search-index`
became a **hot shard** — a disproportionate share of queries (and a heavy aggregation) concentrated
on a single shard, so that shard's node saturated while the rest of the cluster sat nearly idle.
Search latency rose; nothing else in the stack was affected.

## Timeline (UTC)
- 20:05  `search` p99 climbs; users report slow product search.
- 20:14  Cluster CPU is **unbalanced** — one node/shard is pegged while others are light.
- 20:22  Identified: a **hot shard** — query + aggregation skew concentrated load on one shard.
- 20:40  Rebalanced / rerouted hot queries and added a replica to spread read load.
- 21:03  Search latency returns to baseline.

## Root cause
**Data/query skew** made a single shard a hotspot. Because load was uneven, one shard's node
throttled query throughput for everyone hitting that shard, even though aggregate cluster capacity
was fine. This is a **search-index sharding/balance** problem — confined to `search` /
`search-index`, with no connection to checkout, Redis, auth, or the order path.

## Resolution / fix
- **Immediate:** added a replica for the hot shard and rerouted the heavy queries to spread read
  load across nodes.
- **Follow-up:** revisited the shard/routing strategy to avoid concentrating popular keys on one
  shard; added per-shard latency monitoring.

## Lessons learned
- Cluster-wide averages hide a **hot shard** — look at **per-node / per-shard** load. Idle nodes
  next to one pegged node is the tell.
- Slow search is usually an **indexing/sharding** issue inside `search-index`, isolated from the
  checkout and orders subsystems.
