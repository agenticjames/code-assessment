---
id: INC-0955
title: Upstream DNS provider outage causes widespread resolution failures
date: 2026-01-22
severity: SEV2
services: [api-gateway, notifications, search]
duration: 47m
tags: [dns, network, resolution, external, provider-outage]
---

## Summary
For ~47 minutes, services intermittently **could not resolve hostnames**. An **upstream DNS provider
outage** meant name lookups for several external and internal endpoints failed or timed out, so
calls failed *before a connection was even attempted*. The breadth made it look like many things
were broken at once, but the common factor was **DNS**.

## Timeline (UTC)
- 03:11  Sporadic "name resolution failed" / lookup-timeout errors appear across multiple services.
- 03:18  Pattern recognized: failures correlate with **DNS lookups**, not any single service or host.
- 03:24  Upstream **DNS provider** confirms a regional outage affecting resolution.
- 03:40  Switched to a secondary resolver / cached entries; resolution success rate recovers.
- 03:58  Provider restores service; lookups fully normal.

## Root cause
A **third-party DNS provider** outage degraded name resolution. Affected calls failed at the
**lookup** stage — there was nothing wrong with the services, the network paths to them, or any
datastore. The symptom's breadth came from DNS being a shared dependency of everything that makes an
outbound call. This is a **resolution-layer** failure, separate from connectivity or capacity.

## Resolution / fix
- **Immediate:** failed over to a secondary resolver and leaned on cached records to ride out the
  provider outage.
- **Follow-up:** configured redundant resolvers and longer negative-cache tuning so a single DNS
  provider outage cannot take resolution down wholesale.

## Lessons learned
- Wide, simultaneous failures across **unrelated** services with **"cannot resolve / lookup
  timeout"** errors point at **DNS**, not at the individual services. Look for the shared
  resolution-layer cause.
- Treat DNS as a critical shared dependency: run **redundant resolvers** so one provider's outage is
  survivable.
