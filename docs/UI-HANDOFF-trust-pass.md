# UI Handoff — Briefing "trust pass" (6 engine fixes)

**Audience:** the web/UI developer.
**Status:** engine + contract + a first cut of the UI are **done and verified**. This doc tells you
what changed, what's already wired, and what's left for you to polish/verify.

The engine team made six fixes to the investigation output. Four are invisible to you (reasoning
quality); **two add new fields you render**, and one changes what the existing cards look like.

---

## TL;DR — what you actually need to do

1. Pull the new contract (`src/web/lib/contracts.ts`): `InvestigationResult` gained
   **`stakeholder_note: string | null`** and **`noise_dropped: NoiseItem[]`** (`{ item, reason }`).
2. Two new panels are **already rendering** in `components/investigations/briefing.tsx`
   (Stakeholder update + Noise dropped) and the Copy button now copies the engine's note. They work —
   your job is **visual polish + edge cases**, not wiring.
3. Re-style to taste and verify against the reference run (URL below). That's it.

No DB migration, no API change, no new endpoints. The fields ride the existing `verdict` trace event
and `result_json`, so everything flows through the path you already have.

---

## The 6 fixes (context)

| # | Fix | UI impact |
|---|---|---|
| 1 | **Folded "mechanism" hypotheses.** The agent no longer emits a downstream symptom (e.g. "checkout pool exhaustion") as a separate ruled-out hypothesis — it's folded into the confirmed cause's supporting evidence. | **Visible:** briefings now show **fewer, cleaner hypothesis cards** — typically just the confirmed cause + the ruled-out red herring. No more confusing "ruled out at 0.10" card for something that's actually true. Grounding counts often go **up** (folded evidence). |
| 2 | **No "absence" citations.** Missing/empty data goes to `open_questions`, never a fake citation. | Invisible (cleaner grounding numbers). |
| 3 | **Stakeholder note.** New `stakeholder_note` — a paste-ready responder update. | **New panel** (done). |
| 4 | **Confidence capped at 0.95.** A triage first-pass never claims 100%. | **Visible:** confidence bars now max at ~95%, never a full/100% bar. |
| 5 | Regenerated the canonical sample run. | n/a (CLI artifact). |
| 6 | **Noise dropped.** New `noise_dropped[]` — signals considered then dismissed (e.g. a chronic disk alert). | **New panel** (done). |

---

## New data contract

In `src/web/lib/contracts.ts` (already committed):

```ts
export const noiseItemSchema = z.object({ item: z.string(), reason: z.string() });
export type NoiseItem = z.infer<typeof noiseItemSchema>;

export const investigationResultSchema = z.object({
  // ...existing...
  stakeholder_note: z.string().nullish(),       // NEW — paste-ready responder update
  noise_dropped: z.array(noiseItemSchema).default([]), // NEW — [{ item, reason }]
});
```

Both are **backward-compatible**: `nullish` / `default([])` so older runs (which lack the fields)
still parse and simply render nothing. You'll see that in practice — runs created before this change
show no new panels.

**Where the data comes from (FYI, nothing to wire):** the engine's `verdict` event already carries the
full result via `model_dump()`, and `db.finish()` stores the full `result_json`. `LiveRun` reduces the
event stream to `verdict`, which `<Briefing>` renders. The new fields just appear in that object.

---

## What's already wired (review, don't rebuild)

- **`components/investigations/briefing.tsx`** — added two conditional panels after the hypotheses:
  - **Noise dropped** — a labelled list of `{ item — reason }`, muted styling (mirrors "Open questions").
  - **Stakeholder update (paste-ready)** — a bordered card with the note text.
- **`components/investigations/copy-briefing.tsx`** — the top **Copy** button now copies
  `result.stakeholder_note` when present (single source of truth, written from the evidence), and falls
  back to the old client-assembled summary for legacy runs. No fabrication either way.

These follow the existing Tailwind/shadcn patterns in the file, but they're a **first cut** — restyle
freely.

---

## What's left for you (the actual ask)

1. **Visual polish** of the two new panels — spacing, hierarchy, dark mode. The stakeholder card
   currently uses `border bg-card`; the recommended-action card uses `bg-info/10`. Decide the right
   visual weight (the stakeholder note is arguably the most-used output — a responder pastes it into
   Slack).
2. **(Recommended) A dedicated copy button on the stakeholder panel itself.** Right now only the top
   Copy button copies it; an inline copy on the panel is the natural UX. Small add.
3. **Empty/edge states:** `noise_dropped` can be `[]` (panel hidden — correct); `stakeholder_note` can
   be `null` on legacy/inconclusive runs (panel hidden — correct). Confirm both look intentional.
4. **Inconclusive runs:** the stakeholder note is written to hedge ("we cannot yet confirm a cause…").
   Verify it reads well alongside the `INCONCLUSIVE` outcome label.
5. **Confidence bars** now cap at 95% — sanity-check nothing in the bar component assumed a 100% max
   for layout.

---

## How to see it live

A reference run **with the new fields** is already seeded in your dev DB:

```
http://localhost:3000/investigations/f12232f8-8c2a-4be5-bb96-c8c60adcc86b
```

Open it → **Briefing** tab → you'll see the Noise dropped + Stakeholder update panels populated.
(Verified rendering: stakeholder note, recommended action, and noise panels all present; 2 clean
hypothesis cards.)

To generate **fresh** runs with the fields: trigger any scenario with a Gemini key; the live engine
produces all fields.

> Note: runs created **before** this change (e.g. the two ~50-min-old ones in your history) will show
> **no** new panels — that's the backward-compat path working, not a bug.

---

## Files changed (for your review / PR)

**Web (your area):**
- `src/web/lib/contracts.ts` — new `noiseItemSchema`, `stakeholder_note`, `noise_dropped`.
- `src/web/components/investigations/briefing.tsx` — two new panels.
- `src/web/components/investigations/copy-briefing.tsx` — copy the engine note.

**Engine/CLI (context only — no action needed):**
- `src/cli/biggy/engine/schemas.py` — `NoiseItem`, `stakeholder_note`, `noise_dropped`.
- `src/cli/biggy/engine/prompts/adjudicate.md` — folding rule, no-absence rule, 0.95 cap, note + noise.
- `src/cli/biggy/engine/phases/adjudicate.py` — deterministic 0.95 confidence clamp.
- `src/cli/biggy/cli/render.py` — CLI panels (kept in parity with the web).

**Verification done:** web `tsc --noEmit` ✓, eslint ✓ on changed files; CLI ruff ✓, 32/32 engine
tests ✓ (one unrelated pre-existing failure for an in-progress `--json` flag, not from this work); live
Scenario A run confirms all six fixes; browser confirms both panels render.

---

## Before → after (the flagship briefing)

**Before:** 3 hypothesis cards incl. a confusing "H2 — checkout pool exhaustion · ruled out · 0.10"
(true-but-downstream, mislabeled), top confidence **1.00**, no stakeholder note, no noise shown.

**After:** 2 clean cards — **rate-limiter · confirmed · 0.95** and **orders-db · ruled out · 0.05**
(the herring) — **6/6** grounding, a **Noise dropped** line (disk alert), and a paste-ready
**Stakeholder update**.
