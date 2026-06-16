# Biggy CLI (`biggy`)

The Python command-line surface for **Biggy** — an AI on-call incident-investigation copilot.
Phase 1 of the project (see [`../../docs/DESIGN.md`](../../docs/DESIGN.md),
[`../../docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md), [`../../docs/DELIVERY.md`](../../docs/DELIVERY.md)).

> **Status: Inc 0 — walking skeleton.** `investigate` runs a real, end-to-end investigation: it
> loads a workspace, time-scopes the evidence to the incident window, runs a bounded LLM tool-loop
> (LangChain + Gemini) over read-only evidence tools, and prints a grounded briefing with
> line-anchored citations, writing a `ledger.json`. Multi-hypothesis disconfirmation (rule out the
> red herring) and the deterministic citation verifier land in Inc 1 / Inc 2.

## Requirements

- Python **3.11+**.
- A **Gemini API key** (the default provider is `google_genai`).

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
python -m venv .venv
source .venv/bin/activate
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

# investigate scenario A (writes runs/<id>/ledger.json)
biggy investigate "checkout is throwing 504s and customers are complaining" -s A

# also grade the run against the scenario's HIDDEN_TRUTH answer key
biggy investigate "checkout is throwing 504s and customers are complaining" -s A --check
```

Run as a module without the console script: `python -m biggy --help`.

### `investigate` options

| Option | Default | Meaning |
|---|---|---|
| `QUERY` (arg) | — | the incident report / question |
| `--workspace`, `-w` | `acme-checkout` | workspace to investigate within |
| `--scenario`, `-s` | — | scenario id (provides the incident time window), e.g. `A` |
| `--provider` | `google_genai` | LLM provider (LangChain `init_chat_model`) |
| `--model`, `-m` | `gemini-3.1-flash-lite` | model id |
| `--max-steps` | `12` | tool-loop step budget |
| `--out` | `runs/<id>` | directory for `ledger.json` |
| `--check` | off | grade the run vs `HIDDEN_TRUTH` |

## Develop & test

```bash
pytest -q          # offline tests always run; the live engine test is skipped without a key
ruff check . && ruff format --check .
```

## Layout

```
src/cli/
├─ pyproject.toml        # metadata + deps; defines the `biggy` script
├─ biggy/
│  ├─ cli.py             # Typer app + help; registers commands
│  ├─ commands/          # one module per command (investigate, version)
│  ├─ config.py          # RunConfig + workspace-root resolution
│  ├─ vault.py           # workspace/scenario loading + time-scoped evidence
│  ├─ tools/             # read-only evidence tools (list_evidence/read_file/search)
│  ├─ llm/               # provider-abstracted chat client (init_chat_model)
│  ├─ orchestrator.py    # the bounded tool-loop
│  ├─ schemas.py         # Pydantic verdict contracts
│  ├─ ledger.py          # the investigation ledger -> ledger.json
│  ├─ render.py          # rich terminal briefing
│  └─ eval/              # --check grader vs HIDDEN_TRUTH
└─ tests/
```

## Roadmap

The engine grows incrementally — see [`../../docs/DELIVERY.md`](../../docs/DELIVERY.md).
**Inc 1** = multi-hypothesis + disconfirmation (rule out the orders-db herring). **Inc 2** =
deterministic citation verifier + calibrated confidence + `N/N verified` badge.
