---
id: INC-1077
title: Kafka consumer lag delays order processing
date: 2026-04-30
severity: SEV3
services: [orders, kafka, inventory]
duration: 1h14m
tags: [kafka, lag, orders, consumers, async, backlog]
---

## Summary
Order processing fell **behind** for over an hour. Orders were accepted fine at checkout, but the
**async** steps that consume order events from Kafka (inventory reservation, downstream
fulfillment) lagged, so orders sat in a growing backlog before being processed. The customer-facing
write path was healthy; the **consumer side** could not keep up.

## Timeline (UTC)
- 02:10  `kafka_consumer_lag` on the orders topic begins climbing past normal.
- 02:20  Orders appear "stuck": placed successfully but not progressing to processed.
- 02:35  Identified: the orders consumer group is under-provisioned for the current event rate;
         partitions are accumulating an unconsumed backlog.
- 02:50  Scaled out the consumer group (more consumer instances) to drain the backlog.
- 03:24  Lag returns to ~0; the backlog is fully processed; orders catch up.

## Root cause
The orders **consumer group** lacked throughput to match the incoming event rate, so lag built up on
the Kafka partitions. This is an **async backlog / throughput** problem on the consumer side — not a
checkout error, not a database fault, and not a connection issue. Nothing was *failing*; processing
was simply **delayed**.

## Resolution / fix
- **Immediate:** scaled the orders consumer group out to drain the backlog.
- **Follow-up:** autoscale orders consumers on `kafka_consumer_lag`; alert when lag exceeds a
  sustained threshold so a backlog is caught before it becomes customer-visible.

## Lessons learned
- **Consumer lag** is a distinct failure mode: the symptom is **delay**, not errors. Read
  `kafka_consumer_lag` over time rather than looking for 5xx spikes.
- "Orders are slow" can mean the synchronous path is broken **or** the async consumers are behind —
  these are different problems with different fixes (fix the dependency vs. add consumer capacity).
