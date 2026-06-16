# Incremental Delivery Plan

> Companion to [`DESIGN.md`](DESIGN.md). **DESIGN = the *what*** (product, architecture, decisions). **This = the *how/when*** — the order to build in so that *every step ships something you could demo and submit*, never a big-bang reveal at the end.

---

## Why this exists (the agile reframe)

DESIGN.md's `§6` lists commits as a **dependency ladder** — data (C1) → tools (C2) → state (C3) → loop (C4)… You don't see the thing *work* until C4. That's three commits of plumbing with nothing to show — a mild big-bang.

This plan flips it to **vertical slices**: build a thin thread through *every* layer first, get a demo on day one, then make each layer richer and better in small, always-shippable steps.

```
BIG-BANG (horizontal layers)              AGILE (vertical slices)
  data ───────────────┐                     ┌─┬─┬─┬─┬─┬─┐
  tools ──────────────┤                     │0│1│2│3│4│5│  each slice cuts
  state ──────────────┤ first demo          │ │ │ │ │ │ │  through ALL layers,
  loop ───────────────┤   only here →        │d│t│l│o│v│u│  thin → thick
  verify ─────────────┤                     │a│o│o│u│e│x│
  UX ─────────────────┘                     │t│o│o│t│r│ │  demo after EACH
                                            └a┴l┴p┴┴ ┴ ┴ ┘
```

### Principles

1. **Walking skeleton first.** The thinnest end-to-end path (query → crude investigation → cited output) before *any* single layer is "finished." Integration risk dies on day one, not week two.
2. **Vertical, not horizontal.** Each increment cuts thin through data → tools → loop → output. Never "the whole data layer," then "the whole tool layer."
3. **Every increment is demoable *and* submittable.** Stop after any one and you have a coherent thing to show. This is the whole point for a time-boxed take-home.
4. **Risk-first.** Each increment kills the scariest *remaining* unknown (can it find the signal? does it survive a red herring? can we enforce grounding?).
5. **Improve the same artifact.** The `investigate` command exists from Inc 0; every increment makes the *same* command smarter or nicer — progressive enhancement (citations → *verified*; step-logs → *rich trace*; mini-data → *full scenario*).
6. **Solo-appropriate.** "Agile" here means incremental + always-shippable + fast feedback — **not** sprints/standups/story-points. Commit often; **tag each increment** (`v0.1-skeleton`…) so the git history *tells the iterative story* — itself a signal to reviewers.

---

## The progression at a glance

| Inc | Tag | Theme | The CLI/app can now… | Submittable as |
|---|---|---|---|---|
| **0** | `v0.1-skeleton` | Walking skeleton | run a query → **cited hypothesis** over real files | crude floor |
| **1** | `v0.2-reasoning` | Real investigation | reason over Scenario A, **rule out the red herring** | fair |
| **2** | `v0.3-trust` | **Trust layer** | **verify** citations; show confidence + what it *can't* tell | **★ strong-hire (MVP target)** |
| **3** | `v0.4-ux` | The experience | **stream its reasoning live** + polished briefing + stakeholder note | strong-hire, demos great |
| **4** | `v0.5-eval` | Breadth & proof | handle alert-storm + inconclusive cases; **score itself** | "we need this person" |
| **5** | `v0.6-memory` | Memory | **recall & cite** similar past incidents | full Phase-1 story |
| **6** | `v0.7-web` | Web skeleton | trigger from the **browser**, show the briefing | web MVP |
| **7** | `v0.8-live` | Live & tangible | stream the trace in-browser; **click citations → source** | web hero moment |
| **8** | `v0.9-polish` | Polish & graph | show the **blast-radius graph** + investigation history | show-stopper |

**Stop-lines (time-box judgment):** if time is tight, **get to Inc 2** — that's the MVP and the trust thesis is fully delivered. **Inc 3–4** is the sweet spot (beautiful demo + generalization). **Inc 5 + Phase 2** are multipliers. The brief literally prefers "a smaller, thoughtful, working system" over an overbuilt one — so a polished Inc 3 beats a half-finished Inc 8.

---

## Phase 1 — the CLI

### Inc 0 — Walking Skeleton · `v0.1-skeleton`
- **Goal:** prove the whole thread runs — query in, cited hypothesis out, over *real* files.
- **Demo:** `investigate "checkout 504s"` → prints a hypothesis ("rate-limiter config change @14:45") with a citation to a real `file:line`.
- **Vertical slice (thin through every layer):** ~4-file **mini** Scenario A (topology, deployments, redis.log, checkout.log — *signal only, no herring/noise*) · tools `list_evidence`/`read_file`/`search` · single bounded pass (read what you want → emit one hypothesis + evidence as structured output) · ledger = that output saved as `ledger.json` · plain-text terminal output · `investigate "<query>"` entrypoint.
- **Done when:** the command names the rate-limiter change and cites a real source.
- **Deliberately deferred:** red herring, multi-hypothesis, disconfirmation, verification, calibration, rich UI, memory.
- **De-risks:** the #1 unknown — *can the LLM find the signal through tools at all?* Answered on day one.
- **DESIGN:** thin slices of C1–C4. · **Submit-now:** bare end-to-end demo — a floor, not a target.

### Inc 1 — Real Investigation · `v0.2-reasoning`
- **Goal:** genuine agentic reasoning that survives a plausible distractor.
- **Demo:** watch it form **two** hypotheses (rate-limiter vs. migration), pull evidence to discriminate on **timing**, and **rule out the migration** with a stated reason.
- **Slice:** **full** Scenario A (herring + noise + Slack + metrics) · upgrade loop to **hypothesize → test (disconfirm) → adjudicate** · ledger becomes the evolving multi-hypothesis object · crude step-logging printed so you can see it think.
- **Done when:** Scenario A yields rate-limiter as top hypothesis **and** the migration explicitly ruled out (timing + failed rollback).
- **Deferred:** citation *verification*, calibration polish, rich trace, stakeholder note.
- **De-risks:** does the reasoning hold against a red herring — not just find an obvious signal?
- **DESIGN:** completes C1, C4. · **Submit-now:** a fair submission — demonstrably *reasons*, not pattern-matches.

### Inc 2 — Trust Layer · `v0.3-trust` ← ★ MVP TARGET
- **Goal:** make the output *trustworthy* — grounded, calibrated, honest.
- **Demo:** every claim cited; the deterministic **verifier catches a planted bad citation**; briefing shows confidence + contradicting evidence + dropped noise; **ablation** (delete a key file) makes it *lower confidence / raise an open question* instead of fabricating.
- **Slice:** **citation verifier** (re-opens sources, substring-match, flags ungrounded) · calibrated output schema (confidence, contradicting evidence, open questions, ruled-out noise) · **insufficient-evidence path** · `N/N verified` grounding badge.
- **Done when:** every claim verified or flagged; Scenario A briefing shows confidence + contradicting evidence + dropped noise; the ablation behaves honestly.
- **Deferred:** rich live trace, stakeholder-note polish, other scenarios, memory.
- **De-risks:** can we *enforce* grounding, not just request it? The verifier proves yes.
- **DESIGN:** C5 (+ calibration parts of C4/C6). · **Submit-now:** **the strong-hire MVP — the trust thesis fully delivered.** If time is tight, *get here.*

### Inc 3 — The Experience · `v0.4-ux`
- **Goal:** make it a pleasure to watch and read (the "wow" delivery mechanism).
- **Demo:** the full flagship run with a **live streaming `rich` trace** (tool calls, confidence bars updating) → polished briefing + copy-paste **stakeholder note**; a recorded canonical run committed.
- **Slice:** `rich` live trace (upgrades Inc 1's step-logs) · `briefing.md` renderer · stakeholder note · `ledger.json` + `briefing.md` artifacts · recorded sample run in-repo.
- **Done when:** one command streams legible reasoning and prints a clean briefing + stakeholder note; sample run checked in.
- **Deferred:** breadth, eval, memory, web.
- **De-risks:** demo quality.
- **DESIGN:** C6. · **Submit-now:** strong-hire and *demos beautifully* — best ROI stop if the web app is out of reach.

### Inc 4 — Breadth & Proof · `v0.5-eval`
- **Goal:** prove it generalizes and that you *measure* it.
- **Demo:** Scenario B collapses ~20 alerts → 1 root; Scenario C returns a calibrated **55/45 + the missing evidence** it'd need; then `eval` prints a **scorecard** across A/B/C (found cause? herring ruled out? citations valid? calibrated?).
- **Slice:** Scenario B + C datasets · eval harness + scorecard · per-scenario grading vs. the `HIDDEN_TRUTH` answer keys.
- **Done when:** B and C hit their target outputs; `eval` prints a passing scorecard.
- **Deferred:** memory, web.
- **De-risks:** overfitting — proves the engine isn't tuned to one puzzle.
- **DESIGN:** C7, C8. · **Submit-now:** "we need this person" — generalization + *I measure my agent*.

### Inc 5 — Memory · `v0.6-memory`
- **Goal:** the RAG / vector / memory story.
- **Demo:** on a recurring incident (Scenario D) it **retrieves and cites** a similar past incident ("matches INC-0987, same fix"); Scenario A's briefing gains the same recall.
- **Slice:** in-process vector index over incident-library + runbooks · `recall_similar_incidents` wired into the loop · Scenario D.
- **Done when:** agent surfaces & cites INC-0987 on a matching new incident.
- **Deferred:** web (Phase 2).
- **De-risks:** that semantic recall adds signal, not noise.
- **DESIGN:** C9. · **Submit-now:** the complete Phase-1 story — every brief criterion visibly hit.

---

## Phase 2 — the web app

### Inc 6 — Web Skeleton · `v0.7-web`
- **Goal:** thinnest end-to-end *web* thread (walking skeleton, again).
- **Demo:** in the browser, pick Scenario A → click **Investigate** → the final briefing appears (poll, no live stream yet).
- **Slice:** FastAPI wrapper around the engine · Redis job + result store · minimal Next/shadcn page (picker + trigger + briefing render via poll).
- **Done when:** browser trigger → engine runs → briefing shows.
- **Deferred:** live streaming, clickable citations, graph, history.
- **De-risks:** Python-engine ↔ Next integration over Redis.
- **DESIGN:** C10 + thin C11. · **Submit-now:** a working web MVP on top of the CLI.

### Inc 7 — Live & Tangible · `v0.8-live`
- **Goal:** the web hero moment.
- **Demo:** trigger and watch the reasoning **stream** in the browser (Redis pub/sub → SSE/WS); **click a verified citation → the source opens at the line**; grounding badge.
- **Slice:** Redis pub/sub trace events · SSE/WS to the frontend · live trace panel · clickable citations → source viewer · grounding badge.
- **Done when:** live trace streams; citations open sources.
- **Deferred:** graph viz, history, polish.
- **De-risks:** real-time streaming UX.
- **DESIGN:** C11, C12. · **Submit-now:** the show-stopper demo.

### Inc 8 — Polish & Graph · `v0.9-polish`
- **Goal:** the visible-graph payoff + finish.
- **Demo:** **blast-radius graph** (cause chain lit, herring greyed) · investigation **history** list · clean empty/error/loading states.
- **Slice:** blast-radius graph viz from topology + ledger · Redis-backed history · stakeholder-note copy · states.
- **Done when:** graph renders the incident; history works; no rough edges.
- **DESIGN:** C12 (graph), C13. · **Submit-now:** the full vision.

---

## Continuous threads (not increments — woven through every one)

These improve *alongside* each increment rather than as a single commit:

- **Prompt design** — every increment refines the system/agent prompts as you see failure modes. Keep prompts in versioned files, not inline strings.
- **Failure handling** — harden as new failure modes surface (malformed output, missing files, step-budget, ungrounded citations). Don't save it all for one "robustness" commit.
- **Tests** — add alongside, especially for the *deterministic* code where they're cheap and high-value: tools, the verifier, the eval grader.
- **README / run instructions** — keep current every increment; it's an explicit submission requirement, and a stale README undercuts an otherwise great demo.
- **Recorded sample run** — regenerate at each increment so there's *always* a current, submittable demo artifact (and a guard against an embarrassing live-run divergence).

---

## Reconciliation with DESIGN.md §6

- DESIGN's **C1–C13 are the task/architecture breakdown**; this doc's **Inc 0–8 are the *releases*** that group and *reorder* them (thin-slice first).
- The one real reorder: C1–C4 are not built to completion in sequence — **Inc 0 builds *minimal* versions of all four together** to get a day-one demo, then Inc 1+ enriches each. Everything downstream (C5–C13) maps almost 1:1 to increments.
- Commit granularity stays fine (commit often *within* an increment); each **increment** is the demoable checkpoint worth a git tag.
