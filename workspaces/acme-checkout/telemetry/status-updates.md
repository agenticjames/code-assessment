# Public status page — update history (rolling). All times UTC.
# Includes DRAFTS pending confirmation. A draft can be WRONG — it reflects the current (possibly
# mistaken) human theory at the time, not ground truth.

## 2026-06-10 — Authentication degradation (RESOLVED)
- 21:18 [posted] "We're investigating elevated errors across several features." (investigating)
- 21:36 [posted] "Resolved. A configuration change to our authentication service was reverted." (resolved)

## 2026-06-12 — Checkout errors during promo (RESOLVED)
- 10:10 [posted] "Some customers may see errors completing checkout. Investigating." (investigating)
- 10:45 [posted] "Resolved. Elevated traffic briefly exceeded a capacity limit." (resolved)

## 2026-06-16 — Checkout failures (ONGOING)
- 15:00 [DRAFT — pending confirmation, written by dana] "We are investigating checkout failures.
  The likely cause is a database migration performed this afternoon, which we are rolling back.
  We expect resolution shortly."
  > ⚠️ DRAFT ONLY. This blames the 14:00 orders-db migration. NOT yet confirmed — and the migration
  >    rollback at 14:58 did not resolve the 504s. Do not publish until the cause is verified.
