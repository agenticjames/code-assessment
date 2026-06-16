---
id: INC-1003
title: Disk full on the log-aggregator host
date: 2026-03-11
severity: SEV4
services: [log-aggregator]
duration: 2h08m
tags: [disk, logging, infrastructure, chronic, noise]
---

## Summary
The central **log-aggregator** host filled its disk and stopped accepting new log volume for ~2
hours. It is **not** on any customer request path, so there was **no customer impact** — but this is
the origin of the now-chronic `disk-space-low` SEV4 alert that perennially pages and is routinely
ignored during real incidents.

## Timeline (UTC)
- 07:30  `disk-space-low` fires for `log-aggregator` (free space under the 15% threshold).
- 07:45  Confirmed: log retention/rotation fell behind ingestion; the volume filled up.
- 08:20  Freed space (rotated and pruned old logs); ingestion resumes.
- 09:10  Rotation re-tuned; disk back under threshold — but with little steady-state headroom.
- 09:38  Closed. Downgraded from the initial page once confirmed non-customer-impacting (SEV4/SEV3).

## Root cause
Log **retention/rotation** could not keep pace with ingestion growth, so the disk filled. The host
is infrastructure (central logging), **off the customer path**, so the only impact was a gap in log
collection. After re-tuning, the volume **still runs hot** with minimal headroom.

## Resolution / fix
- **Immediate:** rotated/pruned logs to free space; restored ingestion.
- **Follow-up:** re-tuned rotation. Because the disk now sits near the threshold by design, the
  `disk-space-low` SEV4 **fires regularly** and is treated as **known background noise** rather than
  re-paged each time. Proper remediation (a bigger volume) remains unfunded.

## Lessons learned
- This is **why the log-aggregator disk alert is chronically ignored**: it is a known, recurring
  SEV4 on a non-customer-facing host. During a live incident it is almost always **noise to drop**,
  not a lead.
- A persistently-firing low-severity alert trains responders to tune it out — track it as known
  noise so it isn't mistaken for a fresh signal (and so a *genuinely* new disk problem still gets
  noticed).
