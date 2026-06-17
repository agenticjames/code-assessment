# Biggy CLI (`biggy`)

The Python engine + command-line surface for **Biggy** — an AI on-call incident-investigation
copilot (see [`../../docs/DESIGN.md`](../../docs/DESIGN.md),
[`../../docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md), [`../../docs/DELIVERY.md`](../../docs/DELIVERY.md)).

`investigate` runs a real, end-to-end investigation: it loads a workspace, **time-scopes the
evidence** to the incident window (clamped to `as_of` — no hindsight), runs a bounded LLM tool-loop
(**hypothesize → test/disconfirm → adjudicate**) over read-only evidence tools, then a **deterministic
citation verifier** re-opens every cited source and confirms the quote is real. The output is a
grounded briefing with line-anchored citations and an `N/N verified` badge, plus a `ledger.json`.
`biggy eval` scores the engine across scenarios against hidden answer keys.

## Requirements

- Python **3.11+**.
- A **Gemini API key** (default provider `google_genai`). Offline tests run without one.

## Install

From this directory (`src/cli`), in a virtual environment:

```powershell
# Windows / PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

```bash
# macOS / Linux
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Configure

Copy [`../../.env.example`](../../.env.example) to a repo-root `.env` and add your key:

```
GEMINI_API_KEY=your-key-here          # mapped to GOOGLE_API_KEY automatically
# BIGGY_WORKSPACES_ROOT=...            # optional; defaults to the in-repo workspaces/
```

`.env` is git-ignored. The workspace location is **config-driven** (`--workspaces-root` flag >
`$BIGGY_WORKSPACES_ROOT` > the in-repo default) — Biggy does not search parent directories.

## Usage

```bash
biggy --help
biggy version

# seed the frame from scenario A; --check grades it against the hidden answer key
biggy investigate "checkout is throwing 504s and customers are complaining" -s A --check

# the time frame is first-class — investigate as of a moment, looking back a window (no scenario)…
biggy investigate "orders are timing out" --as-of 2026-06-12T10:20:00Z --look-back 30m

# …or a retrospective range
biggy investigate "why was checkout unstable Jun 10-12?" --since 2026-06-10T00:00:00Z --until 2026-06-12T23:59:59Z

# honesty demo: hide the smoking-gun evidence and watch the verifier flag the over-reach
biggy investigate "checkout is throwing 504s ..." -s A --ablate telemetry/logs/redis.log

# I-measure-my-agent: score the engine across scenarios (try -m to compare models)
biggy eval -s A -s B -s C -s E

# regenerate the web's workspace manifest (scenario presets + corpus profile)
biggy workspace manifest acme-checkout
```

Run as a module without the console script: `python -m biggy --help`.

### `investigate` options

| Option | Default | Meaning |
|---|---|---|
| `QUERY` (arg) | — | the incident report / question |
| `--scenario`, `-s` | — | seed the frame + enable `--check` grading from a scenario, e.g. `A` (optional) |
| `--as-of` | now | investigate as of this UTC instant (ISO 8601) |
| `--look-back` | `2h` | window depth from `--as-of`, e.g. `2h` / `90m` / `5d` |
| `--since` / `--until` | — | retrospective range (ISO 8601; use together) |
| `--workspace`, `-w` | `acme-checkout` | workspace to investigate within |
| `--provider` | `google_genai` | LLM provider (LangChain `init_chat_model`) |
| `--model`, `-m` | `gemini-3.1-flash-lite` | model id (the eval sweep found flash models best here) |
| `--max-steps` | `12` | tool-loop step budget |
| `--out` | `runs/<id>` | directory for `ledger.json` |
| `--check` | off | grade the run vs `HIDDEN_TRUTH` (needs `--scenario`) |
| `--ablate PATH` | — | hide an evidence path from the agent (repeatable; honesty demo) |

The **time frame** resolves by precedence: explicit range (`--since`/`--until`) > `--as-of`/`--look-back`
> a `--scenario` seed > the default (now / 2h). A scenario is no longer required — it just *seeds* the
frame and points `--check` at the answer key. `biggy eval` takes `-s/--scenario` (repeatable; default =
all discovered), `-m/--model`, and `--no-detail` (summary matrix only). `biggy workspace manifest <ws>`
regenerates the committed `manifest.json` the web reads.

## Develop & test

```bash
pytest -q          # offline tests always run; the live engine test is skipped without a key
ruff check . && ruff format --check .
```

## Layout

The package is layered so the **engine is surface-agnostic** (it imports no surface); the CLI and a
future API are thin shells over it.

```
src/cli/biggy/
├─ engine/                 # the importable investigation engine
│  ├─ orchestrator.py      #   the phase pipeline
│  ├─ context.py           #   Investigation — the shared blackboard phases mutate
│  ├─ frame.py scenario.py #   TimeFrame + resolve_frame ladder · scenario dir access (seed/answer-key)
│  ├─ config.py schemas.py ledger.py trace.py
│  ├─ grounding.py         #   the deterministic citation verifier (the trust centerpiece)
│  ├─ phases/              #   hypothesize · investigate · adjudicate · verify (one class per stage)
│  ├─ evidence/            #   vault (time-scoping) · timeutil · tools (read_file/search/get_*)
│  ├─ workspace/           #   workspace artifacts — the public manifest generator
│  ├─ llm/                 #   provider-abstracted chat client (init_chat_model)
│  └─ prompts/             #   versioned phase prompts
├─ cli/                    # terminal surface: app · render · commands/(investigate · eval · workspace · version)
└─ eval/                   # grade (vs HIDDEN_TRUTH) · harness (biggy eval)
```

## Roadmap

Phase 1 — **Inc 0–4** (walking skeleton → abductive loop → trust layer → live trace + briefing → eval
harness) — is done, and **Phase 2** shipped too (Inc 6–8: the web app over this same engine). See
[`../../docs/DELIVERY.md`](../../docs/DELIVERY.md) and [`../../docs/PHASE2.md`](../../docs/PHASE2.md).
The one increment still ahead is **Inc 5** — semantic cross-incident memory (the
`recall_similar_incidents` tool + the reserved `idx:incidents` vector index).
