# Architecture

> The **technical build reference**. Companion to [`DESIGN.md`](DESIGN.md) (the *what/why* — product, agent approach, scenarios) and [`DELIVERY.md`](DELIVERY.md) (the *when* — incremental delivery). This doc is the *how it's built*: stack, engine internals, module layout, data flow, Phase 2 wiring.
>
> Working name **Biggy**. No implementation code here — interfaces, contracts, and module shapes only.

---

## 1. Decisions at a glance

| Concern | Decision | Why (one line) |
|---|---|---|
| Language | **Python** (Phase 1 engine + CLI) | best fit for Pydantic-driven structured LLM work |
| LLM framework | **LangChain primitives** — `init_chat_model`, `@tool`, `.with_structured_output()`, `.bind_tools()` | matches the team's stack; buys provider abstraction + tool loop + structured output |
| Orchestration | **plain Python** (NOT LangGraph) | flow is linear with one bounded loop; LangGraph's value-adds (durability/HITL/branching) are unused in Phase 1 |
| Model | **Gemini** via `init_chat_model("google_genai:…")` | provider-swappable by a model-id string / CLI flag |
| Schema contract | **Pydantic** everywhere | one provider-neutral source of truth for structured output + validation/retry |
| Grounding | **deterministic citation verifier** (plain Python, no LLM) | grounding you can't check is grounding you can't trust |
| Observability | **LangSmith** (env-var config, ~0 code) | free tracing/debugging accelerant + fitting for an AI-SRE tool |
| CLI | **Typer** (thin shell) + **`rich`** (live trace) | no logic in the CLI; engine is importable & reused by Phase 2 |
| Retrieval | structured tools within-incident · **semantic index** cross-incident | embeddings only where keywords fail (incident memory) |
| Graphs | topology + ledger, **in-memory** (no graph DB) | right-sized structured context |
| Phase 2 | **FastAPI** wrapper + **Redis** (job/pub-sub/store/vector) + existing **Next.js + shadcn** | engine emits artifacts; web is a trigger + renderer |

**The spine:** *own the brain (reasoning, prompts, verifier, ledger), buy the plumbing (provider abstraction, tool-call mechanics, streaming, tracing).*

---

## 2. System overview

```
PHASE 1 (CLI)                              PHASE 2 (web — wraps the SAME engine)

 investigate "<query>"                      Next.js + shadcn
   --workspace --scenario                      │ trigger / poll / stream
   --provider --model                          ▼
        │                                   FastAPI (thin)
        ▼                                       │ runs engine as a job
 ┌──────────────────────────┐  imports     ┌────┴─────────────┐
 │   ENGINE (biggy pkg)      │◄─────────────│  same engine     │
 │                          │              └────┬─────────────┘
 │  orchestrator (plain Py) │                   │ pub/sub + store
 │  phases · tools · ledger │              ┌────▼─────────────┐
 │  llm client · verifier   │              │     Redis        │ job queue · trace
 │  renderer · memory       │              │  pub/sub · store │ pub/sub · ledger
 └──────────┬───────────────┘              │  vector index    │ store · vectors
            │ emits ARTIFACTS                └──────────────────┘
            ▼
   ledger.json · trace events · briefing.md
   (rendered live in terminal via rich)
```

**The decoupling contract (why Phase 2 is cheap):** the engine knows *nothing* about a frontend. It emits three artifacts — the **Investigation Ledger** (JSON), a **trace event stream** (one event per step), and a rendered **briefing** (Markdown + structured report). The CLI renders these in the terminal; Phase 2 streams + renders them in the browser. Phase 1 logic is never touched in Phase 2.

---

## 3. The engine

### 3.1 Orchestrator — plain Python, linear with one bounded loop

```
investigate(query, workspace, scenario):
    ledger = Ledger.new(query, workspace)
    manifest = vault.load(workspace, scenario)      # Phase 0 — deterministic ingest + topology graph

    hypotheses = hypothesize(query, manifest, ledger)        #  1 structured call   [AGENT]
    investigate_loop(hypotheses, manifest, ledger)           #  the ONE tool loop   [AGENT ★]
    verdict = adjudicate(ledger)                             #  1 structured call   [AGENT]
    verify(verdict, vault)                                   #  citation check      [CODE ★]
    return render(verdict, ledger)                           #  briefing + notes    [CODE]
```

The whole control flow reads top-to-bottom in one function. Each step is a **node-shaped function** — so wrapping these in a LangGraph `StateGraph` later (if Phase 2 needs durability, or we add parallel hypothesis testing) is a near-zero refactor. We don't pay for that until a trigger appears (see §3.6).

### 3.2 Phases

| Phase | Kind | What it does | LLM mechanism |
|---|---|---|---|
| `hypothesize` | AGENT | from symptoms + recent changes + topology + recalled incidents → a *set* of candidate causes (incl. the "obvious" one), each with a `disconfirming_test` | `.with_structured_output(Hypotheses)` |
| `investigate` | AGENT ★ | the bounded tool loop — pulls evidence to **refute** each hypothesis, mutates the ledger | `.bind_tools(...)` + `while` |
| `adjudicate` | AGENT | rank by confidence; rule out refuted; if nothing clears threshold + leads exhausted → declare uncertainty | `.with_structured_output(Verdict)` |
| `verify` | CODE ★ | re-open every cited source; confirm the quoted snippet exists; flag ungrounded claims | none (plain Python) |
| `render` | CODE | briefing + stakeholder note + `ledger.json` from the verdict + ledger | none (templating) |

The key prompt-design principle in `investigate`: *seek evidence that would prove me wrong.* That single directive is what rejects the red herring and resists the Slack consensus (see DESIGN §4.2).

### 3.3 The investigate loop (the one piece of real agency)

```
messages = [system, hypotheses, evidence-so-far]
model = llm.with_tools(TOOLS)            # .bind_tools under the hood
for step in range(max_steps):            # step budget = runaway-failure handling
    ai = model.invoke(messages)
    emit_trace(ai)                       # → rich (CLI) / Redis pub/sub (web)
    if not ai.tool_calls:                # agent decided it's done
        break
    for call in ai.tool_calls:
        result = TOOLS[call.name](**call.args)   # WE dispatch — every citation anchored
        messages.append(ToolMessage(result, source=result.source))
        ledger.record(result)            # state evolves, visibly
```

We deliberately **own this loop** (not Gemini's automatic-function-calling, not a prebuilt agent): it gives us the step budget, per-step trace emission, and grounding control — exactly the things being graded.

### 3.4 LLM client layer (`llm/`)

A thin module over LangChain so the engine never imports a provider SDK directly:

- `client.py` — wraps `init_chat_model(f"{provider}:{model}")`. Exposes:
  - `structured(messages, schema) -> PydanticObj` — via `.with_structured_output(schema)`, with one validation-retry.
  - `with_tools(tools) -> runnable` — via `.bind_tools(tools)` for the loop.
  - `stream(...)` — for the live trace.
- `fake.py` — a **scripted fake model** returning canned tool-calls / structured objects. This is the *second implementation* that validates the interface is provider-shaped-correctly, **and** it's the backbone of deterministic, offline, API-free unit tests of the orchestrator, phases, eval harness, and demo reproducibility.
- **Provider swap** = change the `--provider/--model` flag (or config). No engine changes — delivers the "plug any AI" goal essentially for free.
- **LangSmith** = set `LANGCHAIN_TRACING_V2` + `LANGSMITH_API_KEY` env vars; traces appear with zero code.

### 3.5 Tools layer (`tools/`)

`@tool`-decorated functions over the vault — deterministic, narrow, and **source-attached** (every result carries the `file:line` it came from, so citations are real by construction). No "solve it" tool.

| Tool | Returns |
|---|---|
| `list_evidence()` | manifest: files, types, time ranges |
| `get_topology(service)` | deps / dependents / owner / config pointer (graph traversal) |
| `get_changes(window, service?)` | change/deploy events in a window |
| `read_file(path, filter?)` | content, line-referenced |
| `search(keyword)` | grep hits → `file:line` |
| `get_metric(name, window)` | a metric series (timing correlation) |
| `recall_similar_incidents(signature)` | **semantic** search over the incident-library (§3.8) |

**Structured tools for structured data** (`get_changes`, `get_metric`, `get_topology`); **raw `read_file`/`search` for unstructured** (logs, chat). That split mirrors the data types.

### 3.6 When we'd add LangGraph (the deferred-decision litmus)

| Need | Use |
|---|---|
| durable execution / resume-after-crash | LangGraph |
| human-in-the-loop interrupts | LangGraph |
| branching / parallel fan-out (concurrent hypothesis testing) | LangGraph |
| multi-agent topology | LangGraph |
| **linear flow + one bounded tool loop (← us, Phase 1)** | **plain Python** |

For a linear flow, a `StateGraph` is *more* setup than five calls + a `while`, so it cuts against the velocity goal. The node-shaped functions keep the door open.

### 3.7 State — the Investigation Ledger

The central, append-only, evolving state object (full schema in DESIGN §4.4). Compact shape:

```
incident_id, workspace, query, status
timeline[]      { t, event, source }
evidence[]      { id, claim, snippet, source:"file:line", supports|refutes, confidence }
hypotheses[]    { id, statement, confidence, supporting[], contradicting[],
                  status: open|confirmed|ruled_out, disconfirming_test }
noise_dropped[] { item, reason }
open_questions[]   recommended_actions[]   stakeholder_note
grounding       { claims_total, claims_verified, ungrounded[] }
```

It's a Pydantic model; every mutation appends to a state log → that log *is* the trace event stream and the "evolving memory" artifact.

### 3.8 Retrieval & memory (`memory.py`) — two tiers

1. **Within-incident → structured tools, no embeddings.** A few dozen files in a window: reasoning is the bottleneck, not retrieval.
2. **Cross-incident memory + runbooks → semantic search.** Symptom-signature matching is where keywords fail. In-process index (numpy / FAISS-flat) in Phase 1 → **Redis vector** in Phase 2 (no new dependency). Satisfies RAG + vector + memory with one real use case.

### 3.9 Grounding & verification — two distinct mechanisms

- **Citation verification** (`verify`, deterministic): re-opens each cited source, substring-matches the quoted snippet, flags ungrounded claims. Catches *hallucinated evidence*. → the `N/N verified` grounding score.
- **Hypothesis disconfirmation** (in `investigate`, agentic): actively seek refuting evidence before committing. Catches *premature conclusions*. A directed evidence search — **not** two agents debating.

---

## 4. Repo / module layout

Monorepo: the Python engine lives alongside the existing Next.js app.

```
biggy/
├─ engine/                         # Python package — Phase 1 (the investigation engine)
│  ├─ pyproject.toml
│  ├─ src/biggy/
│  │  ├─ cli.py                    # Typer entrypoint (thin shell) — investigate "<query>" --flags
│  │  ├─ orchestrator.py           # the plain-Python control flow (§3.1)
│  │  ├─ llm/  client.py  fake.py  # provider abstraction + test fake (§3.4)
│  │  ├─ phases/  hypothesize.py  investigate.py  adjudicate.py  verify.py  render.py
│  │  ├─ tools/   __init__.py  (the @tool evidence primitives, §3.5)
│  │  ├─ prompts/ hypothesize.md  investigate.md  adjudicate.md   # versioned, not inline
│  │  ├─ schemas.py                # Pydantic: Hypothesis, Evidence, Verdict, Briefing…
│  │  ├─ ledger.py                 # the Investigation Ledger + append-only log
│  │  ├─ vault.py                  # workspace/scenario loading + evidence manifest
│  │  ├─ memory.py                 # semantic incident-memory index
│  │  └─ trace.py                  # trace event emission (rich + Redis pub/sub)
│  └─ tests/  test_tools.py  test_verify.py  test_orchestrator.py(fake LLM)  test_eval.py
├─ workspaces/                     # the data vault (DESIGN §3) — acme-checkout/...
├─ api/                            # Phase 2 — FastAPI wrapper (thin; imports engine)
├─ src/                            # existing Next.js + shadcn app (Phase 2 frontend)
└─ docs/  DESIGN.md  DELIVERY.md  ARCHITECTURE.md
```

The CLI is a thin shell; `--provider/--model` surface the seam; the engine is importable so Phase 2's API reuses it unchanged.

---

## 5. Phase 2 — web app

The engine wrapped in a thin API; the existing Next.js + shadcn app becomes trigger + viewer.

```
Next.js (shadcn) ──POST /investigate──► FastAPI ──► engine runs as background job
       ▲  ▲                                │
       │  └── SSE / WebSocket ◄── Redis pub/sub (live trace events) ◄──┘
       └───── GET /investigations/:id ◄── Redis (ledger + report store)
```

**Redis earns its place (one component, four jobs):** job queue · pub/sub streaming the live reasoning trace to the browser · store/cache for ledgers + reports · **vector search** for the semantic memory index (so the vector store is a Redis feature, not a new dependency).

**Frontend:** workspace/scenario picker · trigger → **live streaming trace** · briefing card (ranked hypotheses + confidence, supporting/contradicting evidence, ruled-out, open questions, recommended action, stakeholder note) · **clickable verified citations → source viewer** · **blast-radius graph** (topology with the causal chain lit, herring greyed — the visible payoff of the in-memory graph) · `✅ N/N verified` badge.

No engine changes — Phase 2 only triggers it and renders its artifacts.

---

## 6. Cross-cutting concerns

- **Config** — secrets via env (`GOOGLE_API_KEY`, `LANGSMITH_API_KEY`); behavior via CLI flags (`--provider`, `--model`, `--workspace`, `--scenario`, `--max-steps`). The engine takes a config object; the CLI/API populate it.
- **Failure handling** — structured-output validation + one retry (Pydantic); tool errors fed back to the agent as `ToolMessage`, not crashes; step-budget stop; insufficient-evidence path (state it, don't fabricate); ungrounded citations demoted/flagged by the verifier.
- **Testing** — the **fake LLM** enables deterministic, offline unit tests of the orchestrator/phases; `verify` and the tools are pure Python → cheap high-value tests; the **eval harness** runs all scenarios and scores them against each `HIDDEN_TRUTH` answer key (found cause? herring ruled out? citations valid? calibrated?).
- **Observability** — LangSmith traces (every LLM call, tokens, latency) + the engine's own trace event stream.
- **Determinism for demos** — low temperature + robust scenario design so the conclusion is stable; a recorded canonical run committed so a reviewer's run can't diverge embarrassingly.

---

## 7. Architecture decision record (rationale, condensed)

1. **Python engine, importable, behind a thin CLI** — same engine powers Phase 2; CLI holds no logic.
2. **LangChain primitives, not LangGraph (Phase 1)** — linear flow + one bounded loop; LangGraph deferred behind the §3.6 litmus. Matches the team's stack without hiding the reasoning.
3. **Own the loop, not a prebuilt agent** — step budget, per-step trace, grounding control are exactly the graded artifacts.
4. **Gemini via `init_chat_model`** — provider-swappable by config; no provider SDK in the engine.
5. **Pydantic as the schema contract** — provider-neutral; backbone of structured output + validation/retry.
6. **Deterministic citation verifier in plain code** — the "where AI shouldn't be" decision; turns grounding from a claim into an enforced property.
7. **Two in-memory graphs, no graph DB; semantic search only for incident memory** — right-sized structured context + embeddings only where keywords fail.
8. **Engine emits artifacts (ledger / trace / briefing)** — decouples Phase 1 from Phase 2; makes the web app a renderer.
9. **Fake LLM adapter** — validates the provider seam + enables deterministic tests and reproducible demos.
