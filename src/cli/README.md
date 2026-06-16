# Biggy CLI (`biggy`)

The Python command-line surface for **Biggy** — an AI on-call incident-investigation copilot.
This is Phase 1 of the project (see [`../../docs/DESIGN.md`](../../docs/DESIGN.md) and
[`../../docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md)).

> **Status: scaffold.** The thin Typer shell — commands + help are wired, but the investigation
> engine (LLM orchestration, tools, ledger, citation verifier) is **not built yet**. `investigate`
> currently validates and echoes its run config; it performs no file, network, or LLM access.

## Requirements

- Python **3.11+** (developed against 3.11.9).

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

This installs the `biggy` console command (plus pytest, via the `dev` extra).

## Usage

```bash
biggy --help                  # top-level help; lists commands
biggy --version               # print version

biggy version                 # version + Python runtime

biggy investigate "checkout is throwing 504s and customers are complaining" --scenario A
biggy investigate "<query>" --json     # machine-readable output
```

You can also run it as a module without installing the script:

```bash
python -m biggy --help
```

### `investigate` options

| Option | Default | Meaning |
|---|---|---|
| `QUERY` (arg) | — | the incident report / question |
| `--workspace`, `-w` | `acme-checkout` | workspace to investigate within |
| `--scenario`, `-s` | — | scenario id (e.g. `A`) |
| `--provider` | `google_genai` | LLM provider (LangChain `init_chat_model`) |
| `--model`, `-m` | `gemini-2.0-flash` | model id |
| `--max-steps` | `12` | tool-loop step budget |
| `--json` | off | emit JSON instead of rich output |

The flags mirror [`../../docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) §6 so wiring the engine
in later is a drop-in change.

## Develop & test

```bash
pytest -q
```

## Layout

```
src/cli/
├─ pyproject.toml        # project metadata + deps; defines the `biggy` script
├─ biggy/
│  ├─ cli.py             # Typer app + help; registers commands
│  ├─ __main__.py        # `python -m biggy`
│  └─ commands/          # one module per command (investigate, version)
└─ tests/                # CLI smoke tests
```

## Roadmap

The engine lands incrementally on top of this shell — see
[`../../docs/DELIVERY.md`](../../docs/DELIVERY.md) (Inc 0 = walking skeleton).
