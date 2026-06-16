# #incidents — Acme Checkout war room (rolling transcript, UTC)

> One continuous channel. Slice it by date range to see what was discussed in a window.
> Bots: `pagerduty` (pages), `deploybot` (deploy notices).

## 2026-06-10
[18:33] deploybot: dep-2d71 search synonyms deployed (theo)
[21:06] deploybot: dep-3a8c auth-service config deployed (lena) — memory limit 2Gi→1Gi
[21:10] pagerduty: 🚨 alerts firing across cart, checkout, orders, user-profile… (cascading)
[21:11] mei: war room open. this looks broad — what's going on?
[21:12] raj: checkout's throwing 401s and "auth check timed out". checkout itself looks healthy otherwise
[21:13] theo: search and reco erroring too — all auth timeouts
[21:14] pagerduty: 🚨 auth-service pod OOMKilled
[21:15] lena: auth pods are crashlooping. looks like memory
[21:16] dana: orders db side is fine, it's the auth validation that's failing
[21:20] lena: hold on — checkout, cart, orders, search, reco, user-profile, notifications… every one of these calls auth-service. this is all one thing, not seven
[21:22] lena: auth got a memory-limit cut at 21:05 (dep-3a8c, 2Gi→1Gi). it's OOMing under normal load
[21:24] mei: if that's it, reverting should bring everything back. do it
[21:25] lena: reverting dep-3a8c
[21:31] raj: 401s dropping across the board
[21:35] mei: auth recovered, downstream clearing. the storm was one config change; the other ~19 alerts were symptoms. same shape as INC-1095
[21:41] mei: 👏 nice catch lena. postmortem tomorrow

## 2026-06-11
[13:06] deploybot: dep-c0e5 cdn cache rule deployed (sam)

## 2026-06-12
[08:31] deploybot: dep-1a44 feature-flags promo banner enabled (priya)
[10:00] theo: promo email blast just went out, traffic ramping hard
[10:01] pagerduty: 🚨 redis connection pool near capacity; checkout 5xx
[10:02] raj: checkout connection errors — "couldn't get a connection from pool"
[10:03] sam: redis conns pegged at 50/50. promo kicked off at 10:00, traffic ~5x baseline
[10:05] priya: shared pool's maxed — rate-limiter + checkout + cart all sit on it. feels like the Valentine's incident
[10:08] sam: shedding non-critical load and bumping maxclients
[10:40] sam: conns back to normal, errors clearing. surge-driven pool exhaustion — same family as INC-0987
[10:45] dana: orders connection errors cleared too 👍

## 2026-06-13
[15:41] deploybot: dep-d4a9 search relevance tuning deployed (theo)

## 2026-06-14
[03:05] sam: checkout pods looked bloated on memory overnight — did a rolling restart, memory's back down. worth watching
[09:50] raj: ty sam. checkout p99 has looked a touch high this week, I'll keep an eye

## 2026-06-15
[16:14] dana: sporadic 500s on orders for the last ~15min. can't repro it on demand though 😕
[16:18] dana: nothing deployed today — last orders deploy was the 9th
[16:22] sam: a few of those 500s say "downstream call timed out after 3000ms". flaky dependency? kafka maybe
[16:25] dana: doesn't name which downstream though, and we're not sampling traces on these (trace_id is "-")
[16:27] theo: orders memory looks spiky too — could be GC pauses? heap hit ~81% around 16:22
[16:28] dana: maybe, but GC logging is disabled on orders, so I can't confirm a pause
[16:34] theo: so it's either memory/GC or a downstream timeout, and honestly the evidence fits both about equally
[16:40] mei: I'm not calling a root cause on this. enable GC logging + bump trace sampling, then watch for the next spike
[16:41] dana: agreed — it's basically 50/50 right now

## 2026-06-16
[08:16] pagerduty: 🚨 search 5xx high
[08:15] deploybot: dep-5b71 search v2.9 deployed (theo)
[08:18] theo: search 500s kicked off right after my 08:15 deploy — could be me, digging in
[08:40] deploybot: dep-5b71 rolled back (theo)
[08:43] theo: error rate's back to baseline. empty-query NPE I introduced, my bad 🙈
[11:25] raj: fyi checkout's felt sluggish the last few days, p99 slowly creeping. nothing deployed though — on my radar
[14:00] deploybot: mig-0616 orders-db migration started (dana) — add idx_orders_customer
[14:45] deploybot: dep-7e2a rate-limiter config deployed (sam)
[14:47] pagerduty: 🚨 checkout 5xx high; p99 breaching SLO; redis connections saturated
[14:48] raj: checkout 504s, customers complaining — payment spins then errors
[14:49] mei: war room, SEV1. what changed in the last hour?
[14:51] dana: we ran the orders-db migration at 14:00. timing's suspicious — could be that. I'll roll it back
[14:52] dana: rolling back the migration
[14:55] raj: checkout logs show "timeout acquiring connection from pool" — looks DB-ish to me too
[14:58] dana: migration rollback done… still 504s 🤔
[15:01] raj: yeah still erroring. so it's not the migration?
[15:03] priya: fwiw checkout's latency curve lines up almost exactly with the rate-limiter push at 14:45 (dep-7e2a), not the 14:00 migration
[15:04] sam: ignore the disk alert on log-aggregator btw — it's been firing for days, always does
[15:05] dana: maybe, but the migration's the only schema change today — that's still my bet; the rollback may not have fully settled
[15:07] raj: agreed, let's clear the db angle before chasing a config tweak
[15:09] raj: still 504ing, customers still hitting it
[15:13] mei: still open — the rollback didn't clear it and the rate-limiter timing is only a maybe. keep digging, no root cause called yet
[15:16] dana: ok, db's clean — query latency's been flat the whole time. it is NOT the migration
[15:18] priya: redis connected_clients is pegged at 50 — the rate-limiter's been churning the shared pool since 14:45. it's dep-7e2a
[15:20] mei: that's it — priya flagged the timing early and got talked over. roll back dep-7e2a
