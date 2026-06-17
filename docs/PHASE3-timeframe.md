# Phase 3 — Decouple the incident time frame from `--scenario`

> Status: **COMPLETE** (Phases 0–5 + final sweep). This is the living reference for the time-frame
> work. All phases landed, verified, and old code deleted. See the progress log (§7).

## 1. Problem

`--scenario` does three jobs at once:

1. provides the incident **time frame** (`as_of` + `look_back`),
2. points at the **answer key** (`HIDDEN_TRUTH.md`) for grading,
3. names the canned **query**.

These are separable. Grading reads only the answer key + ledger (`eval/grade.py`), never the
window. The window is built in exactly one place (`vault.py` `_load_scenario`). Only one phase reads
it directly (`phases/hypothesize.py`). So we split scenario into **a frame seed** + **an answer-key
pointer**, and make the time frame a first-class input.

## 2. Architecture (the two new primitives)

### 2.1 `TimeFrame` — the single time concept

```
TimeFrame:
  as_of:     datetime               # the clamp ("now" for live; range-end for retrospective)
  window:    (start, end)           # what the Vault slices to; end == as_of
  mode:      "live" | "retrospective"
  look_back: str | None             # live only (e.g. "2h"); None for an explicit range
```

Produced by **one** resolver, `resolve_frame(config)`, with this precedence ladder:

1. explicit range (`since`/`until`) → retrospective frame `window=[since, until]`, `as_of=until`
2. explicit `as_of` and/or `look_back` → live frame (`as_of` defaults to `now()`)
3. `scenario` present, no explicit frame → seed from that scenario's frame (live **or** retro)
4. nothing → live default `now()` / `2h`

`resolve_frame` is the **only** place a window is computed. It lives in the engine because only the
engine knows "now" and telemetry clamping.

### 2.2 `manifest.json` — the single source for frame seeds + corpus data

Committed per workspace at `workspaces/<ws>/manifest.json`, engine-generated, **answer-key-free**:

```jsonc
{
  "workspace": "acme-checkout",
  "scenarios": [
    { "id": "A", "label": "504s", "query": "...", "mode": "live",
      "as_of": "2026-06-16T15:15:00Z", "look_back": "2h" },
    { "id": "G", "label": "retro range", "query": "...", "mode": "retrospective",
      "range": { "from": "2026-06-10T00:00:00Z", "to": "2026-06-12T23:59:59Z" } }
  ],
  "corpus": { "min": "2026-06-08T...", "max": "2026-06-16T...", "density": [ ... ] }
}
```

**Why a manifest is forced (not speculative):** the web's read boundary (`lib/workspace.ts`) denies
`scenarios/`, so the web structurally cannot read `query.yaml`. The engine — which already owns the
telemetry timestamp parsing and the scenario directory — generates it. This also kills the
hand-duplicated 7-item list in `lib/scenarios.ts`.

### 2.3 Where resolution lives (the DRY rule)

- **Authoritative** window resolution happens once, in the engine (`resolve_frame`). The worker
  writes the resolved frame to the DB.
- The web's `lib/timeframe.ts` is an **explicitly-labelled preview-only mirror** — the same trivial
  `as_of − look_back` arithmetic that `contracts.ts` already mirrors, guarded by the parity test. It
  never persists a guess; it only previews the band for the timeline.

## 3. Locked decisions (2026-06-16)

- **Manifest freshness:** commit `manifest.json` + a CI test that regenerates and diffs (fail on
  drift). No build-time/per-request generation.
- **Scope:** Phases 0–4 (live mode end-to-end + timeline). Phase 5 (G's `multi_incident` grader) is a
  follow-up; the engine will *run* G via a retro frame, but `--check` on G stays incomplete.
- **`as of` input:** native `<input type="datetime-local">`, no new deps. Treat its value as **UTC**
  (corpus is UTC-anchored: `workspace.yaml timezone: UTC`) — display a `UTC` suffix and convert on
  read, or the window is off by the user's tz offset.

## 4. Phases, files & acceptance

Verbs: **NEW** create · **CHANGE** edit existing seam · **REUSE** untouched dependency · **DELETE**.

### Phase 0 — The spine (foundation)

Goal: define the contract everything else builds on. No user-visible change. **DONE.**

- [x] NEW `engine/scenario.py` — `ScenarioSeed` + the single door to scenario dirs (seed/answer-key/iter).
- [x] NEW `engine/frame.py` — `TimeFrame` + `resolve_frame(config)` + `now()` seam.
- [x] NEW `engine/workspace/manifest.py` — `build_manifest(workspace_dir)` → dict (scenarios + corpus).
- [x] NEW `cli/commands/workspace.py` — `biggy workspace manifest <ws>` writes `manifest.json`.
- [x] CHANGE `engine/config.py` — `RunConfig` += `as_of`/`look_back`/`since`/`until` (frame.py needs them).
- [x] CHANGE 7× `scenarios/*/query.yaml` — added canonical `label:` (the DRY source for preset chips).
- [x] NEW `workspaces/acme-checkout/manifest.json` — generated + committed.
- [x] CHANGE `worker/contracts.py` — `Job` += `as_of?`, `look_back?`, `since?`, `until?` (all optional).
- [x] CHANGE `web/lib/contracts.ts` — `jobSchema` mirror += same fields; `scenario` event += `mode`.
- [x] CHANGE `tests/test_contract_parity.py` — assert **Job field-set** parity (today: event names only).
- [x] NEW `tests/test_manifest_fresh.py` — regenerate manifest, diff vs committed, fail on drift.
- [x] NEW `tests/test_frame.py` — all four ladder rungs incl. retrospective + precedence + helpers.
- [x] REUSE `engine/evidence/timeutil.py` (`parse_iso`, `parse_lookback`, `extract_timestamp`).

Acceptance: ✅ manifest valid (7 scenarios, corpus min/max/density); ✅ 73 tests pass; ✅ ruff clean;
✅ web typecheck clean.

### Phase 1 — Backend frame plumbing

Goal: engine investigates from an explicit frame; scenario optional; grading gates on the answer key. **DONE.**

- [x] CHANGE `engine/config.py` — `RunConfig` += `as_of`, `look_back`, `since`, `until` (done in P0).
- [x] CHANGE `engine/evidence/vault.py` — `Vault.load()` takes a `TimeFrame` from `resolve_frame`;
      the `Scenario` dataclass is gone; the Vault now exposes `frame` (when) + `query`/`severity`/
      `scenario_id` (what). The "scenario required" raise is deleted; `_wlabel` → `frame.label()`.
- [x] CHANGE `engine/phases/hypothesize.py` — reads `vault.frame` + `vault.query`, not `vault.scenario`.
- [x] CHANGE `engine/context.py` — Ledger `as_of`/`window`/`incident_id` fed from the `TimeFrame`.
- [x] CHANGE `engine/trace.py` — `scenario` event payload += `mode`.
- [x] CHANGE `cli/commands/investigate.py` — `--as-of` / `--look-back` / `--since` / `--until`;
      `--scenario` optional; `--check` resolves the answer key via `scenario.hidden_truth_path` (no Vault).
- [x] CHANGE `worker/runner.py` — passes Job frame inputs into `RunConfig` (resolution stays in engine).
- [x] CHANGE `worker/db.py` — `finish()` writes `as_of`/`window_start`/`window_end` from the ledger.
- [x] CHANGE `eval/harness.py` — grades via `scenario.hidden_truth_path` (Vault no longer needed there).
- [x] CHANGE `tests/test_vault.py` — old "scenario required" test now asserts the default live frame.

Acceptance: ✅ offline smoke — live (as_of/look_back, no scenario), retrospective (since/until), and
scenario-seed all resolve; user query overrides seed; ✅ `investigate --help` lists the flags;
✅ 73 tests pass; ✅ ruff + web typecheck clean. (Worker DB write verified by column-name match to
Drizzle schema; the live round-trip test is Postgres-gated.)

### Phase 2 — Web foundation (vertical slice)

Goal: a frame typed in the web reaches the worker and the DB — before any fancy UI. **DONE.**

- [x] NEW `web/lib/manifest.ts` — zod schemas + types for `manifest.json` (`ScenarioSeed`, `CorpusProfile`, `Manifest`).
- [x] NEW `web/lib/timeframe.ts` — `FrameInput` + `DEFAULT_LOOK_BACK` + `LOOK_BACK_OPTIONS` +
      `lookBackMs()` + `previewWindow()` + `frameFromSeed()` (the preview-only mirror of `frame.py`).
- [x] CHANGE `web/lib/format.ts` — added `formatInstant(iso)` + `windowLabel()` (deterministic UTC).
- [x] CHANGE `web/lib/workspace.ts` — `readManifest(workspace)` (reuses `readSource`'s boundary).
- [x] CHANGE `web/lib/actions.ts` — reads frame from FormData → validates via `jobSchema` → XADD;
      INSERT seeds `asOf`/window only when explicit (worker overwrites authoritatively).
- [x] CHANGE `web/lib/contracts.ts` — `jobSchema` frame fields (done in P0); types confirmed.
- [→] `web/lib/scenarios.ts` deletion **moved to Phase 3** (its consumer, the composer, is rebuilt
      there — keeps the build green between phases).

Acceptance: ✅ `pnpm typecheck` + `pnpm lint` green; `actions.ts` is frame-aware end-to-end. The
visible UI round-trip is exercised in Phase 3 (composer sends the fields).

### Phase 3 — Composer redesign (decompose the monolith)

Goal: focused, testable sub-components; time frame first-class. **DONE.**

- [x] NEW `web/components/investigations/composer/index.tsx` — owns form state, composes children;
      mirrors the frame into hidden fields for the server action.
- [x] NEW `.../composer/time-frame-control.tsx` — Live/Range segmented toggle + `as of` (UTC) +
      `Now` + `look back` select / range inputs. Pure controlled component.
- [x] NEW `.../composer/scenario-presets.tsx` — manifest-driven chips; a pick fills report + frame.
- [~] ~~`grading-toggle.tsx`~~ **DROPPED** — the web has no grading path (the worker runs the
      investigation; grading is a CLI/`eval` capability). A grading checkbox would be a dead control.
      Documented here as a deliberate scope decision; web grading would be a separate feature.
- [x] DELETE old monolithic `composer.tsx` + the hand-duplicated `lib/scenarios.ts`; page now reads
      the manifest (`readManifest`) and passes it to `<Composer manifest={…}>`.
- [x] NEW `lib/timeframe.ts` UTC helpers (`isoToLocalInput`/`localInputToIso`/`nowIso`) for the
      datetime-local-as-UTC gotcha.
- [x] REUSE `ui/select`, `ui/badge`, `ui/input`, `ui/button`, `cn()`; native `datetime-local`.

Acceptance: ✅ browser-verified — composer renders; 7 manifest presets; Live/Range toggle works;
preset A fills a live frame (`as_of` 15:15, `look_back` 2h, UTC correct); preset G fills a
retrospective range; **full submit → Postgres INSERT with `as_of`/`window_start`/`window_end`
populated** (+ Redis XADD); no console errors; typecheck + lint green.

### Phase 4 — Timeline strip + display surfaces

Goal: the visual hero + surfacing the frame on run/trace views. **DONE.**

- [x] NEW `.../composer/incident-timeline.geometry.ts` — pure ts→pixel math (à la `blast-radius.graph.ts`):
      band (min-width clamp), as-of x, hidden region, sqrt-scaled density ticks.
- [x] NEW `.../composer/incident-timeline.tsx` — SVG strip (band + clamp line + shaded hidden region +
      density), corpus/window labels, legend. `useSyncExternalStore` for the client-only clock read
      (no hydration mismatch, no setState-in-effect). Wired into `time-frame-control.tsx`.
- [x] CHANGE `.../run-header.tsx` + `live-run.tsx` + `[id]/page.tsx` — thread + show the resolved window.
- [x] CHANGE `.../trace-event-item.tsx` — `scenario` line now shows `window/range <label> · N files`.
- [~] No web test runner exists; geometry is pure (unit-testable later). Verified live in the browser.

Acceptance: ✅ browser-verified on the live stack — A renders a thin band at `13:15–15:15` with the
no-hindsight region shaded `15:15→18:00`; G renders a wide `Jun 10–Jun 12` band with a large clamp
region; 60 density ticks; corpus + window labels correct; run detail page renders with no console
errors; typecheck + lint clean. (Screenshot capture hangs in this harness — verified via a11y
snapshot + DOM reads instead.)

### Phase 5 — Adjacent completion (follow-up, after 0–4) — **DONE**

- [x] CHANGE `eval/grade.py` — added the `multi_incident` branch (G): both incidents surfaced, a
      distinct hypothesis per incident (no conflation), every event's citations, noise, grounding.
      Range-scoping is structurally enforced by the vault's windowing. + 2 grade tests (pass/fail).
- [x] CHANGE `src/cli/README.md` — frame flags, `--scenario` as an optional seed, the precedence
      ladder, `biggy workspace manifest`, refreshed layout tree. (`workspaces/acme-checkout/README.md`
      already documented the `as_of`/`range` model accurately — no change needed; DESIGN.md not stale.)

Acceptance: ✅ 75 Python tests pass (incl. 2 new G-grader tests against the real HIDDEN_TRUTH); ruff
clean. (A live graded G run needs a Gemini key; the grader logic is verified against the answer key.)

## 5. Old code to delete (end-of-build sweep) — **ALL DONE**

- [x] The "a --scenario is required" raise in `vault.py` (gone; replaced by `resolve_frame`).
- [x] The hand-duplicated `SCENARIOS` array + whole `web/lib/scenarios.ts` file (deleted).
- [x] The monolithic `web/components/investigations/composer.tsx` (replaced by `composer/`).
- [x] The `Scenario` dataclass + its `as_of`/`look_back`/`window` fields (gone; `TimeFrame` owns time).
- [x] `Vault._load_scenario` + `_wlabel` (replaced by `resolve_frame` + `TimeFrame.label()`).
- [x] Stale `test_vault` "scenario required" assertion (now asserts the default live frame).
- [x] Grading's dependence on the Vault (`investigate --check` / `eval` read the answer key directly).

Verified clean: a repo-wide grep finds no `_load_scenario` / `vault.scenario` / `_wlabel` /
`lib/scenarios` references outside this doc's prose. `ruff check` + `ruff format` (my files) +
`pnpm typecheck` + `pnpm lint` + `pnpm build` all green; 75 Python tests pass.

## 6. DRY scorecard (one home per concept)

| Concept | Single home | Consumers |
|---|---|---|
| Window resolution (authoritative) | `engine/frame.py:resolve_frame` | vault, worker, eval |
| Duration parsing | `engine/evidence/timeutil.py` | frame, vault |
| Scenario seeds + corpus data | `workspaces/<ws>/manifest.json` | web presets, web timeline |
| Job wire shape | `worker/contracts.py` ↔ `lib/contracts.ts` (parity test) | web, worker |
| Frame DB columns | `lib/db/schema.ts` (already exist) | worker writes, web reads |
| Web look-back options / defaults / preview math | `lib/timeframe.ts` | control, timeline, header |
| Display formatting | `lib/format.ts` | all web views |
| Timeline layout math | `incident-timeline.geometry.ts` | timeline component |

## 7. Progress log

- 2026-06-16 — Plan written. Baseline: 59 Python tests pass. Web deps installed.
- 2026-06-16 — **Phase 0 done.** Added `engine/scenario.py` (one door to scenario dirs),
  `engine/frame.py` (`TimeFrame` + `resolve_frame` ladder + `now()`), `engine/workspace/manifest.py`
  + `biggy workspace manifest` cmd, committed `manifest.json`, `label:` in 7 query.yaml. Extended
  `Job` + `jobSchema` with frame inputs; parity test now asserts Job field-set. 73 Python tests pass
  (59→73), ruff + web typecheck clean. Not yet wired into the running engine (that's Phase 1).
- 2026-06-16 — **Final sweep done.** All old code deleted (sweep grep clean). Full verification
  green on both stacks: 75 Python tests, `ruff check` + `ruff format` (my files), `pnpm typecheck`
  + `pnpm lint` + `pnpm build` (all routes), live worker-DB round-trip (frame persisted), browser
  smoke (composer + timeline, live + retrospective). Pre-existing `ruff format` drift on 2 untouched
  files (`schemas.py`, `test_comms.py`) left alone — a ruff-version artifact, not this change.
  **Feature complete.**
- 2026-06-16 — **Phase 5 done.** `eval/grade.py` now grades G's `multi_incident` (timeline of two
  distinct incidents, each cited; conflation fails) — 2 new tests, 75 total pass. CLI README updated
  for the frame flags + manifest command; dataset README already accurate.
- 2026-06-16 — **Phase 4 done.** Timeline strip (`incident-timeline.{geometry.ts,tsx}`) renders the
  window on the corpus with the shaded no-hindsight region + density; wired into the time-frame
  control. Run header + trace line now surface the window. Browser-verified live: A (thin band, clamp
  at 15:15) and G (wide Jun10–12 band, large clamp region) both correct; no console errors; typecheck
  + lint clean. Strengthened the no-setState-in-effect path with `useSyncExternalStore`.
- 2026-06-16 — **Phase 3 done.** Composer decomposed into `composer/{index,time-frame-control,
  scenario-presets}.tsx`; old monolith + `lib/scenarios.ts` deleted; page feeds the manifest down.
  Grading toggle deliberately dropped (no web grade path). Verified live in the browser against the
  compose stack: presets fill the frame (live + retrospective), UTC handled, and a real submit wrote
  the frame columns to Postgres. Also strengthened `test_worker_db` to assert frame persistence (now
  passes against live PG). typecheck + lint clean.
- 2026-06-16 — **Phase 2 done.** Web foundation: `lib/manifest.ts` (manifest zod schema/types),
  `lib/timeframe.ts` (the preview-only frame mirror: `FrameInput`, `LOOK_BACK_OPTIONS`,
  `previewWindow`, `frameFromSeed`), `lib/format.ts` (+`formatInstant`/`windowLabel`),
  `lib/workspace.ts` (+`readManifest`), `lib/actions.ts` now frame-aware (forwards inputs, seeds the
  window columns when explicit). typecheck + lint green. `scenarios.ts` deletion deferred to Phase 3.
- 2026-06-16 — **Phase 1 done.** Vault now takes a resolved `TimeFrame` (the `Scenario` dataclass +
  the "scenario required" raise are deleted); `frame`/`query`/`severity`/`scenario_id` exposed.
  Rewired context/trace/hypothesize; grading (`investigate --check`, `eval/harness`) reads the answer
  key via `scenario.hidden_truth_path` with no Vault. CLI gained `--as-of/--look-back/--since/--until`;
  worker passes them through and `db.finish` persists the resolved window. 73 tests pass, ruff + web
  typecheck clean. Offline smoke confirms live + retro + seed paths. (Note: `investigate.py` lost its
  `BIGGY_FAKE_RUN` block mid-session — unrelated to this work, already gone on the branch.)
