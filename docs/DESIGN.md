# Incident Investigator — Design & Build Plan

> Working name: **Biggy**. An AI on-call triage copilot that investigates messy production incidents and produces a **briefing you can trust** — every claim cited and machine-verified, every hypothesis tested against disconfirming evidence, uncertainty stated honestly.

**Status:** design locked, pre-build.
**Context:** Biggy AI Engineer take-home (`docs/task/`). Phase 1 = Python CLI. Phase 2 = shadcn web app + Redis.

---

## 0. TL;DR — the thesis

Everyone will build "chat with your logs" or a multi-agent swarm that confidently names a root cause. Both are the traps the brief warns against (agent theater / research project).

We build the one thing that's actually hard and actually valuable: **an investigator an on-call engineer would trust at 3am.** Trust = grounding (cited + code-verified evidence), calibration (says how sure, says when it can't tell), and transparency (you watch it reason). The product is organized end-to-end around earning that trust.

The reasoning engine is an LLM, but it is *disciplined by deterministic code*: the control flow, the dependency-graph traversal, and — critically — a citation verifier that the LLM cannot bluff past. That division of labor is the direct answer to the brief's closing line: *"deciding where AI is useful and where deterministic code is better."*

---

## 1. Product definition (high level)

**What it is.** A CLI (Phase 1) and thin web app (Phase 2) that take a vague incident report and a workspace of operational evidence, run a bounded, hypothesis-driven investigation, and emit a grounded briefing: ranked hypotheses with confidence, supporting **and** contradicting evidence, ruled-out noise, open questions, a recommended next action, and a plain-English stakeholder update.

**Who it's for.** The first responder to a page. The output is a *first briefing* that saves the human the first 20 minutes of flailing — not a final post-mortem.

**The core promise (and how we keep it):**

| Promise | Mechanism |
|---|---|
| Don't make me trust a black box | Live reasoning trace; every claim carries a `source:file:line` + verbatim snippet |
| Don't lie to me | Deterministic **citation verifier** re-opens each source and confirms the snippet exists; ungrounded claims are flagged, not shown as fact |
| Don't be confidently wrong | **Abductive loop** seeks *disconfirming* evidence before committing; multi-hypothesis output with confidence |
| Tell me when you don't know | Calibrated "insufficient evidence" path → states the missing evidence instead of inventing a cause |

**What success looks like.** A reviewer runs one command, watches it pull evidence *because of* what it just found, watch it **reject a plausible red herring with a reason**, watch it **admit one thing it couldn't determine**, and close with `✅ 11/11 claims verified`. That trio is the "this person gets it" moment.

**Non-goals (deliberately not building):** a full incident-management product, auto-remediation / acting on prod, a generic chatbot, a heavyweight graph DB or vector store, real integrations to live infra (reproducibility > realism of plumbing).

---

## 2. Use cases (the demo surface)

One workspace (**"Acme Checkout"**, an e-commerce stack), several incidents you trigger by typing a vague report. Each scenario is engineered to demonstrate a *different* capability the brief grades, and each has a one-line demo query.

| # | Demo query (what you type) | Hidden cause | Red herring / noise | Capability proven | Difficulty |
|---|---|---|---|---|---|
| **A** | *"checkout throwing 504s, customers complaining"* | rate-limiter config `max_tokens 100→10` → shared Redis pool exhaustion → 504s | **Herring:** DB migration 47min earlier (symptoms *look* like DB). **Noise:** chronic disk alert. **Human noise:** Slack blames the migration | Dependency-direction reasoning; reject herring; resist human consensus; **memory** (matches a prior incident) | Medium ★ flagship |
| **B** | *"we're getting paged by ~20 alerts, what's actually going on?"* | one upstream dependency (auth service) degrades → cascade of downstream alerts | The 19 downstream alerts are all symptoms; 1 is the cause | Signal-from-noise **at scale**; alert correlation/dedup → collapse storm to root | Medium (volume) |
| **C** | *"intermittent 500s for the last hour, can't reproduce"* | genuinely ambiguous — two plausible causes the evidence can't fully separate | The disconfirming evidence (GC metrics / downstream logs) is *absent from the vault on purpose* | **Calibrated uncertainty**; "I'm 55/45, here's what I'd need" — the anti-overfitting showcase | Hard (epistemics) |

**Why three.** A proves grounded reasoning under ambiguity; B proves it scales to noise; C proves it knows its limits. Together they prove the system *reasons* rather than pattern-matching one planted answer — which kills the overfitting worry a single scenario invites.

**Beyond the core three:**
- **D — "didn't we see this before?"** an explicit *recurring* incident → the showcase for **semantic incident-memory** (a core capability, §4.5): "matches INC-0987, same fix." Built in C9.
- **Second workspace** (different domain, e.g. a data-streaming pipeline) → the true *with-more-time* multiplier; proves the engine isn't hardcoded to one topology. Lives in the eval harness.

---

## 3. Data model

### 3.1 Workspace vs. scenario (the key separation)

- **Workspace** = the company's *standing* operational world. Changes rarely. This is the persistent context + memory.
- **Scenario** = a *time-bounded incident* inside a workspace. This is what the agent investigates.

This separation is itself a design statement: it mirrors reality (one company, many incidents), makes prior-incident memory genuinely cross-scenario (real retrieval, not a bolted-in file), and lets one agent handle many incidents in one world (generalization).

```
workspaces/
  acme-checkout/
    workspace.yaml              # name, description
    topology/services.yaml      # dependency graph (the "knowledge graph", lightweight)
    teams.yaml                  # ownership, on-call
    runbooks/*.md               # standing operational knowledge
    incident-library/           # PRIOR incidents → semantic memory corpus
      INC-0987.md
      INC-1042.md
    scenarios/
      A-checkout-504/
        scenario.yaml           # the query, time window, + HIDDEN_TRUTH.md (graded answer key, not fed to agent)
        alerts/alerts.json
        logs/{api-gateway,checkout,redis,rate-limiter,log-aggregator}.log
        metrics/{checkout_p99,redis_connections,ratelimit_rejects}.csv
        changes/deployments.yaml
        changes/rate-limiter.config.diff
        chat/incident-war-room.md
      B-alert-storm/ ...
      C-intermittent-500/ ...
```

**Standing (workspace) assets:** topology, teams, runbooks, incident-library.
**Per-incident (scenario) assets:** alerts, logs, metrics, changes, chat — all scoped to the incident's time window.

### 3.2 Topology = the lightweight knowledge graph

`services.yaml` is a dependency graph the agent **traverses as a tool** (not a graph DB). The load-bearing detail is shared infra:

```yaml
checkout:      { depends_on: [rate-limiter, redis, orders-db, payment-gateway], owner: team-payments, slo: "p99<800ms" }
rate-limiter:  { depends_on: [redis], owner: team-platform, config: rate-limiter.config.yaml }
redis:         { type: cache, max_connections: 50, shared_by: [rate-limiter, checkout] }   # ← lets the agent connect throttle→pool→checkout
orders-db:     { type: postgres, owner: team-data }
```

### 3.3 Clue-distribution principles (this is *level design* — the project lives or dies here)

1. **The causal chain must be reconstructible but never stated.** No single file says "rate limiter caused pool exhaustion." Breadcrumbs are spread across the diff, the redis log, the metrics timing, and the runbook.
2. **Symptoms point at the herring.** Checkout logs show *DB timeouts* → looks like the migration. The truth is upstream (Redis/rate-limiter). A naive keyword-matcher lands on the migration — exactly like the humans in Slack. Only timing + dependency-direction reasoning gets it right.
3. **Plant disconfirming evidence for the herring.** Migration completed 14:12; latency onset 14:47; a **failed rollback at 14:58** that didn't fix anything = hard proof it's innocent.
4. **Plant a dismissed-but-correct human clue.** Someone notices the rate-limiter timing in Slack and gets talked over. Rewards careful reading; tests resistance to consensus.
5. **Include true noise** (chronic disk alert, pre-incident) that must be *explicitly dropped*, not silently ignored.
6. **For Scenario C, deliberately omit** the evidence that would resolve the ambiguity — the correct output is calibrated uncertainty.

Sample texture:
```diff
# changes/rate-limiter.config.diff   (deploy dep-7e2a @14:45)
- max_tokens: 100
+ max_tokens: 10
```
```
# logs/redis.log
14:48:02 WARNING max number of clients reached (50/50)
```
```
# chat/incident-war-room.md
[14:52] dana:  we ran the orders-db migration at 14:00 — pretty sure that's it. rolling back.
[14:58] dana:  rollback done… still 504s? 🤔            ← proof the migration ISN'T it
[15:03] priya: checkout latency lines up almost exactly with the rate-limiter deploy at 14:45, not the migration
[15:04] sam:   ignore the disk alert btw, log-aggregator always does that
```

---

## 4. Agent approach (the core AI decision)

> **Your question: is the loop the best approach, or a knowledge graph, or hypothesize-then-prove?**
> **Verdict: a hypothesis-driven *abductive* loop, traversing a lightweight dependency graph as a tool, with semantic incident-memory and code-verified grounding.** Not a graph *DB*. Not pure ReAct. Not pure RAG. (On "are we doing embeddings / graphs?" — **yes to both, right-sized**: see §4.5 and §4.8.)

### 4.1 Why this shape (and why not the alternatives)

| Option | Verdict | Why |
|---|---|---|
| Pure ReAct loop ("read stuff until done") | Necessary but insufficient | Wanders, no principled stopping condition, can stop early or stuff context with noise |
| **Full knowledge graph / graph DB** (Neo4j, extracted causal edges) | **Rejected at this scale** | The *extraction* of a KG from messy data is itself the hard problem; storage isn't our bottleneck, *reasoning* is. We take the KG's one real benefit — causal-direction traversal — by modeling topology as a small queryable graph **tool** — in fact we build *two* lightweight graphs (§4.8). (Writeup: "here's where a graph DB *would* earn its place — huge topology, cross-incident entity resolution.") |
| Pure RAG + summarize | Rejected as the spine | Retrieval isn't the problem at this corpus size; an unstructured summary produces a confident blob with no calibration, no disconfirmation, no contradiction tracking |
| **Hypothesis-driven abductive loop** | **Chosen** | Mirrors how real SREs/detectives work; *directs* the search (test theories, don't read everything); natively produces the desired output (multiple hypotheses, supporting + contradicting evidence, confidence, ruled-out); has a principled stop condition |

### 4.2 The loop: Hypothesize → Test (disconfirm) → Adjudicate

This is the "comes up with hypotheses, then has to prove them" structure — sharpened to *disprove*, which is what gives it teeth.

```
Phase 0  INGEST            build evidence manifest + load topology graph            [CODE]
            │
            ▼
Phase 1  HYPOTHESIZE       from symptoms + recent changes + topology + prior        [AGENT]
            │              incidents → generate a SET of candidate causes
            │              (deliberately include the "obvious" one)
            ▼
Phase 2  TEST / LOOP       for each live hypothesis, ask "what evidence would        [AGENT ★]
            │              REFUTE this?" → go get it via tools → update confidence.
            │              Each tool call is caused by the last finding. Bounded
            │              by a step budget (= runaway-failure handling).
            ▼
Phase 3  ADJUDICATE        rank by confidence; rule out refuted; if nothing clears   [AGENT]
            │              threshold and leads are exhausted → declare uncertainty
            ▼
Phase 4  VERIFY            re-open every cited source; confirm snippet exists;       [CODE ★]
            │              flag ungrounded claims (one repair retry, then mark)
            ▼
Phase 5  RENDER            briefing + stakeholder note from the ledger              [CODE]
```

The two ★ steps are the whole thesis: **one genuinely agentic, disconfirmation-directed loop, wrapped in code that keeps it honest.** The key prompt-design principle in Phase 2 is *seek evidence that would prove me wrong* — that single instruction is what rejects the red herring and resists the Slack consensus.

> **Non-theater litmus:** if a reviewer could replace the loop with one `grep` + one "summarize" call and get the same output, it's theater. Here the chain is load-bearing: `topology → recent changes → timing discriminates → mechanism (config diff) → runbook links throttle→pool → metrics confirm pool saturation`. Remove the loop and it collapses to the wrong (migration) answer.

### 4.3 Tools (the agent's hands — deterministic, narrow, source-attached)

No "solve it" tool. Just evidence-access primitives that always return content *with its source*, so every citation is real and verifiable.

| Tool | Returns |
|---|---|
| `list_evidence()` | manifest: files, types, time ranges |
| `get_topology(service)` | deps / dependents / owner / config pointer (graph traversal) |
| `get_changes(window, service?)` | change/deploy events in a time window |
| `read_file(path, filter?)` | content, line-referenced |
| `search(keyword)` | grep hits across the vault → `file:line` |
| `get_metric(name, window)` | a metric series (for timing correlation) |
| `recall_similar_incidents(symptom_signature)` | **semantic** search over the incident-library — where embeddings earn their keep (§4.5) |
| `record_finding(claim, snippet, source, supports/refutes, confidence)` | mutates the ledger (the agent's memory) |

### 4.4 State / memory — the Investigation Ledger (shape, not code)

An append-only object that *evolves* each step. Persisting the mutation log makes "evolving investigation state" a concrete, demonstrable artifact — the diff *is* the narrative.

```
incident_id, workspace, query (raw), status
timeline[]:          { t, event, source }
evidence[]:          { id, claim, snippet, source:"file:line", supports|refutes: hyp_id, confidence }
hypotheses[]:        { id, statement, confidence,
                       supporting:[evidence_id], contradicting:[evidence_id],
                       status: open|confirmed|ruled_out,
                       disconfirming_test: "what evidence would refute this" }
noise_dropped[]:     { item, reason }
open_questions[]:    string                       # the honest gaps
recommended_actions[]: { action, rationale, evidence_id }
stakeholder_note:    string
grounding:           { claims_total, claims_verified, ungrounded:[...] }
```

Ledger evolution (the story, visible):
```
after HYPOTHESIZE          →     after TEST
A rate-limiter   0.40            A rate-limiter   0.78  ✅ chain complete
B db-migration   0.40            B db-migration   0.05  ❌ ruled out (timing + failed rollback)
noise_dropped:   []              noise_dropped:   [disk-space SEV4]
open_questions:  []              open_questions:  [no canary logs for dep-7e2a]
```

### 4.5 Retrieval & embeddings — two tiers (technique vs. infrastructure)

Separate the *technique* (semantic search) from the *infrastructure* (a vector DB). We use the technique where it genuinely wins; we don't stand up a dedicated vector-DB service for a few hundred docs.

1. **Within-incident evidence → structured tools, no embeddings.** A few dozen files in a time window: the bottleneck is reasoning, not retrieval. Structured tools + keyword + whole-file reads give precision at zero embedding latency. Embeddings here would *add* dilution, not remove it.
2. **Cross-incident memory + runbooks → semantic search (a core capability, not a footnote).** Matching a *new* incident's symptom signature to past incidents is the textbook meaning-match problem where keywords fail — "connection pool exhausted" vs "max clients reached" vs "ran out of connections" are one failure class, different words. This single feature satisfies **RAG + vector search + memory** at once, with a real use case. Backed by an **in-process index** (numpy/FAISS-flat) in Phase 1 and **Redis vector search** in Phase 2 — no new dependency, since Redis is already justified for the job queue + live trace. It powers the recurring-incident demo (Scenario D) and enriches Scenario A's briefing ("this matches INC-0987, same fix").

*Considered and mostly rejected:* semantically **clustering** Scenario B's alert storm. Tempting, but structured fields (service / error-type / time) likely cluster more precisely than embeddings here — so we'd reach for embeddings only if the structured signal proved too weak. (Noting the considered-but-rejected option is itself the judgment the brief grades.)

### 4.6 Two distinct verification mechanisms (don't conflate)

- **Citation verification (deterministic, Phase 4):** does the cited snippet actually appear in the named source? Catches *hallucinated evidence*. This is code, and it's the line a reviewer remembers.
- **Hypothesis disconfirmation (agentic, Phase 2):** actively seek evidence that would *refute* the leading theory before committing. Catches *premature/wrong conclusions*. Implemented as a directed evidence search, **not** two agents debating (that would be theater).

### 4.7 Failure handling (an explicit grading criterion)

- Malformed LLM output → schema-validated (Pydantic), one repair retry, then graceful degrade.
- Tool asked for a missing file → structured error fed back to the agent, not a crash.
- Step budget exceeded → stop and report best-effort + uncertainty.
- Evidence insufficient → **state it** (Scenario C path); never fabricate a cause.
- Ungrounded citation survives verify → claim demoted/flagged in the report, not presented as fact.

### 4.8 Structured graphs — we're already building two (just not in a graph DB)

The question was never "graph or no graph" — it's **graph database vs. in-memory structured graph**, and at this scale in-memory wins. We build two:

1. **Static topology graph** (`services.yaml`: services + `depends_on`), traversed as a tool. This *is* "structured operational context," and causal-direction reasoning ("what's *upstream* of checkout?") *is* a graph walk. It's what lets the agent reason past the symptom (DB timeouts) to the upstream cause (rate-limiter → shared Redis pool).
2. **Dynamic causal graph** = the ledger's **hypothesis ↔ evidence ↔ timeline** links (§4.4). We *do* build a causal structure of the incident — we just store it as the ledger, not in Neo4j.

So the "knowledge graph / structured context" criterion is met by the **right-sized representation**, and skipping a graph DB is a *deliberate non-choice* — it earns its place at huge topologies or cross-incident entity resolution; name that boundary in the writeup. (The GraphRAG-style KG+embeddings hybrid is exactly the over-build the brief warns against here.)

**Phase 2 payoff:** render the topology + the incident's **blast radius** as an actual graph (rate-limiter → redis → checkout lit up; the migration herring greyed out). That makes the graph *visible* to the reviewer for almost no cost — it's just drawing data we already have. It's the graph's equivalent of the clickable-citation payoff.

---

## 5. Architecture

> Detailed build reference (stack, engine internals, module layout, Phase 2 wiring) lives in [`ARCHITECTURE.md`](ARCHITECTURE.md). This section is the in-context overview.

### 5.1 The contract that decouples the two phases

The Phase 1 engine emits **structured artifacts** and knows nothing about a frontend:
- the **Investigation Ledger** (JSON),
- a **trace event stream** (one event per step: tool call, finding, hypothesis update),
- a rendered **briefing** (Markdown + the structured report JSON).

Phase 2 is *only* a trigger + renderer over those artifacts. This is why the web app is cheap and why Phase 1 logic is never touched in Phase 2.

### 5.2 Phase 1 — Python CLI engine

```
investigate "<query>"  --workspace acme-checkout  --scenario A
        │
   ┌────▼─────────────────────────────────────────────┐
   │ Orchestrator (deterministic): phases, step budget │
   │   Tools layer ── over the vault (source-attached) │
   │   LLM reasoner ── hypothesize / test / adjudicate │
   │   Ledger ── evolving state, append-only log       │
   │   Verifier ── citation check (code)               │
   │   Renderer ── briefing + stakeholder note         │
   └────┬──────────────────────────────────────────────┘
        ▼
   live trace in terminal (rich) + ledger.json + briefing.md
```

- **Language/stack:** Python; **LangChain primitives** (`init_chat_model`, `@tool`, `.with_structured_output()`, `.bind_tools()`) orchestrated in **plain Python** (not LangGraph — see ARCHITECTURE §3.6); **Gemini** via `init_chat_model("google_genai:…")`, provider-swappable; Pydantic as the schema contract; `rich` for the live trace; Typer for CLI; LangSmith for tracing.
- **Determinism for demos:** low temperature + strong scenario design so the conclusion is stable; commit a recorded sample run so a reviewer's run can't diverge embarrassingly.

### 5.3 Phase 2 — shadcn web app + Redis

> **As-built:** the shipped Phase 2 dropped FastAPI — **Next.js is the API/BFF** — and uses
> **Postgres** as the durable store with **Redis** for queue + live trace (a Python worker runs the
> engine). The sketch below is the original design; [`PHASE2.md`](PHASE2.md) is what was built.

The engine wrapped in a thin API; the existing Next.js + shadcn app becomes the trigger + viewer.

```
Next.js (shadcn) ──POST /investigate──► FastAPI ──► engine runs as background job
       ▲  ▲                                │
       │  └── SSE / WebSocket ◄── Redis pub/sub (live trace events) ◄──┘
       └───── GET /investigations/:id ◄── Redis (ledger + report store/cache)
```

**Redis earns its place** (not decoration): job queue for triggered runs · pub/sub to stream the live reasoning trace to the browser (the hero moment) · store/cache for ledgers + reports · **vector search** for the semantic incident-memory index — so the vector store is a Redis feature we already pay for, not a new dependency. (Pleasing coincidence: the flagship scenario is *about* Redis pool exhaustion.)

**Frontend (shadcn):**
- Workspace + scenario picker (the demo menu of incidents).
- **Trigger → live streaming trace panel** (watch it reason, confidence bars animate).
- **Briefing card:** ranked hypotheses w/ confidence, supporting + contradicting evidence, ruled-out noise, open questions, recommended action, stakeholder note (copy button).
- **Clickable verified citations → source viewer** opens the file at the cited line — grounding made tangible. This is the web-native payoff of the Phase 1 verifier.
- **Blast-radius graph** — the topology with the incident's causal chain lit up and the red herring greyed out (the visible payoff of §4.8).
- A `✅ N/N claims verified` grounding badge.

---

## 6. Phased build plan (one commit per level)

Vertical slices: get Scenario A working end-to-end (C1–C6) before adding breadth. Each commit is demonstrable.

> **Build order lives in [`DELIVERY.md`](DELIVERY.md)** — it groups these commits into demoable, always-submittable increments (walking-skeleton first). This section is the task/architecture breakdown; read DELIVERY.md for the *sequence to build in*.

### Phase 1 — Python CLI

| Commit | Deliverable | Done when |
|---|---|---|
| **C1** | `acme-checkout` workspace + **Scenario A dataset** (topology, alerts, logs, metrics, changes, chat, runbook, prior incident) + `HIDDEN_TRUTH.md` answer key | You can manually trace query→cause from the files; the story is coherent and the herring/noise are present |
| **C2** | Evidence **tools** + manifest over the vault, source-attached results | Each tool works on Scenario A; unit-tested |
| **C3** | **Ledger** model + append-only state log + persistence | Can build/mutate/serialize a ledger; transitions logged |
| **C4** | **Hypothesis-driven loop** (hypothesize→test→adjudicate), LLM + tools, bounded, structured output ← *first end-to-end slice* | Running Scenario A yields the rate-limiter cause **and** rules out the migration |
| **C5** | **Citation verifier** + report annotation | Every claim's snippet verified vs source; ungrounded flagged |
| **C6** | **Report renderer** (briefing + stakeholder note) + **CLI live trace** (rich) | `investigate "<query>"` streams reasoning + prints briefing + grounding badge |
| **C7** | **Scenario B** (alert storm) + **Scenario C** (inconclusive) datasets | B collapses storm→cause; C returns calibrated 55/45 + missing-evidence ask |
| **C8** | **Eval harness** (run all scenarios → scorecard: root cause? herring ruled out? citations valid? calibrated?) | `eval` prints a passing scorecard across scenarios |
| **C9** | **Semantic incident memory** — in-process vector index over incident-library + runbooks (→ Redis vector in Phase 2) + recurring **Scenario D** | Agent retrieves & cites INC-0987 on a matching incident; enriches Scenario A's briefing |

### Phase 2 — Web app

| Commit | Deliverable | Done when |
|---|---|---|
| **C10** | **FastAPI + Redis** wrapper: trigger endpoint, background job, pub/sub trace events, ledger/report store | POST query → engine runs → events on Redis → report retrievable via API |
| **C11** | **Next/shadcn** shell: workspace/scenario picker, trigger, **live trace** via SSE/WS | Pick scenario, click, watch it reason in the browser |
| **C12** | **Briefing UI** + **clickable verified citations → source viewer** + grounding badge | Full briefing renders; clicking a citation opens the source at the line |
| **C13** | Polish: investigation **history** (Redis-backed), stakeholder-note copy, empty/error/loading states | Demo-ready end to end |

**MVP line:** C1–C6 is the strong-hire floor (Scenario A, end-to-end). C7–C9 are the intended **core** build-out — breadth (B/C), *I-measure-my-agent* (eval), and **semantic memory** (the RAG/vector/memory story). Phase 2 + a second workspace are the true "with more time" multipliers.

---

## 7. Appendix

### 7.1 Coverage map — feature → what the brief grades

| Brief criterion | Where we hit it |
|---|---|
| Agent orchestration | Phase 0–5 orchestrator; bounded hypothesis loop |
| Prompting & prompt design | "seek disconfirming evidence" objective; structured hypothesis output |
| Tool use | deterministic source-attached evidence tools |
| Memory / state | evolving append-only Ledger + cross-incident semantic memory |
| RAG / retrieval / vector DB | semantic search over incident-library + runbooks; in-process index → **Redis vector** (Phase 2); real use case = symptom-signature match (§4.5) |
| Knowledge graph / structured context | **two** structured graphs — topology (traversed as a tool) + the ledger's hypothesis↔evidence graph; right-sized, no graph DB; blast-radius viz in Phase 2 (§4.8) |
| Evidence grounding | snippet citations + **code verifier** |
| Failure handling | schema-retry, tool errors, step budget, insufficient-evidence path |
| Practical UX | live trace (CLI + web), clickable citations, stakeholder note |
| Simple-code vs agentic tradeoffs | the CODE/AGENT split is explicit per phase (§4.2) |
| Handling ambiguity & uncertainty | multi-hypothesis + calibration + Scenario C |
| Useful, not theater | non-theater litmus (§4.2); load-bearing reasoning chain |

### 7.2 Open decisions (revisit before/while building)

- LLM model + whether to cache the canonical run for bit-reproducible demos.
- Adversarial verification pass (a "skeptic" mode per hypothesis) — rigor upgrade vs. scope; keep it a *directed evidence search*, never a debate, to avoid theater.
- Scenario B's exact topology (which shared dependency cascades) — design its clue distribution with the same care as A.
- ~~Where the semantic index lives in Phase 2~~ → **decided: Redis vector** (already in the stack, no new dependency); in-process index (numpy/FAISS-flat) for Phase 1. Embedding model still TBD.

### 7.3 Submission write-up angles (for the take-home)

Frame every choice as an *intentional tradeoff*: lightweight dependency graph **as a tool** vs. graph DB (and where a graph DB earns its place); structured tools for evidence vs. embeddings, with semantic search reserved for the one place it wins (incident memory); deterministic verifier because *grounding you can't check is grounding you can't trust*; CLI-first engine emitting artifacts so the web app is a pure renderer. Knowing **where the simple approach breaks** beats claiming it's perfect.
