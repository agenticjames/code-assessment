# Biggy CLI (`biggy`)

The Python engine + command-line surface for **Biggy** — an AI on-call incident-investigation
copilot (see [`../../docs/DESIGN.md`](../../docs/DESIGN.md),
[`../../docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md), [`../../docs/DELIVERY.md`](../../docs/DELIVERY.md)).

`investigate` runs a real, end-to-end investigation: it loads a workspace, **time-scopes the
evidence** to the incident window (clamped to `as_of` — no hindsight), runs a bounded LLM tool-loop
(**hypothesize → test/disconfirm → adjudicate**) over read-only evidence tools, then a **deterministic
citation verifier** re-opens every cited source and confirms the quote is real. The output is a
grounded briefing with line-anchored citations and an `N/N verified` badge, plus a `ledger.json`.
`biggy eval` scores the engine across scenarios against hidden answer keys. See a recorded run in
[`../../docs/sample-run/`](../../docs/sample-run).

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

# investigate scenario A; --check grades it against the hidden answer key
biggy investigate "checkout is throwing 504s and customers are complaining" -s A --check

# honesty demo: hide the smoking-gun evidence and watch the verifier flag the over-reach
biggy investigate "checkout is throwing 504s ..." -s A --ablate telemetry/logs/redis.log

# I-measure-my-agent: score the engine across scenarios (try -m to compare models)
biggy eval -s A -s B -s C -s E
```

Run as a module without the console script: `python -m biggy --help`.

### `investigate` options

| Option | Default | Meaning |
|---|---|---|
| `QUERY` (arg) | — | the incident report / question |
| `--scenario`, `-s` | — | scenario id (provides the incident time window), e.g. `A` |
| `--workspace`, `-w` | `acme-checkout` | workspace to investigate within |
| `--provider` | `google_genai` | LLM provider (LangChain `init_chat_model`) |
| `--model`, `-m` | `gemini-3.1-flash-lite` | model id (the eval sweep found flash models best here) |
| `--max-steps` | `12` | tool-loop step budget |
| `--out` | `runs/<id>` | directory for `ledger.json` |
| `--check` | off | grade the run vs `HIDDEN_TRUTH` |
| `--ablate PATH` | — | hide an evidence path from the agent (repeatable; honesty demo) |

`biggy eval` takes `-s/--scenario` (repeatable; default = all discovered), `-m/--model`, and
`--no-detail` (summary matrix only).

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
│  ├─ config.py schemas.py ledger.py trace.py
│  ├─ grounding.py         #   the deterministic citation verifier (the trust centerpiece)
│  ├─ phases/              #   hypothesize · investigate · adjudicate · verify (one class per stage)
│  ├─ evidence/            #   vault (time-scoping) · timeutil · tools (read_file/search/get_*)
│  ├─ llm/                 #   provider-abstracted chat client (init_chat_model)
│  └─ prompts/             #   versioned phase prompts
├─ cli/                    # terminal surface: app · render · commands/(investigate · eval · version)
└─ eval/                   # grade (vs HIDDEN_TRUTH) · harness (biggy eval)
```

## Roadmap

Phase 1 — **Inc 0–4** (walking skeleton → abductive loop → trust layer → live trace + briefing → eval
harness) — is done, and **Phase 2** shipped too (Inc 6–8: the web app over this same engine). See
[`../../docs/DELIVERY.md`](../../docs/DELIVERY.md) and [`../../docs/PHASE2.md`](../../docs/PHASE2.md).
The one increment still ahead is **Inc 5** — semantic cross-incident memory (the
`recall_similar_incidents` tool + the reserved `idx:incidents` vector index).
