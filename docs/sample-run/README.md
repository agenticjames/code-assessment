# Sample run — Scenario A (checkout 504s)

A recorded canonical investigation, committed so a reviewer's own run has a reference to compare
against. Produced by (from `src/cli/`, with a `GEMINI_API_KEY` in the repo-root `.env`):

```bash
biggy investigate "checkout is throwing 504s and customers are complaining" \
  -s A -m gemini-3.1-flash-lite --check
```

- [`briefing.txt`](briefing.txt) — the terminal briefing + the `--check` scorecard.
- [`ledger.json`](ledger.json) — the engine's full evolving state: the initial hypotheses, every
  tool call, the adjudicated verdict, and the deterministic grounding result.

**What it demonstrates:** the engine confirms the **rate-limiter** config change (`dep-7e2a`) as the
root cause, **rules out the orders-db migration herring** on timing + DB health, every cited claim
passes the deterministic citation verifier (**5/5 verified**), and the scorecard scores it **6/6**
against the hidden answer key.

LLM output is not bit-identical run to run; this is the reference artifact (temperature 0, model
pinned to `gemini-3.1-flash-lite`, which the eval sweep found best for this engine).
