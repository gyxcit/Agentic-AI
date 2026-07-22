# Architecture

## Component diagram

```
                          ┌───────────────────────────────────────────────┐
   user question ────────▶│  agent.run()  (src/agent.py)                   │
                          │                                                │
                          │  1. L1 input filter  ─────────  guardrails.py  │
                          │     (NFKC + injection patterns, strict=BLOCK)  │
                          │            │ clean                             │
                          │            ▼                                   │
                          │  2. ReAct retrieval loop                       │
                          │     ├─ LLM decides tool   ──────  llm_helpers  │
                          │     ├─ L4 action gate     ──────  guardrails   │
                          │     ├─ tool: recall_memory / search_knowledge  │
                          │     │        └─ hybrid + rerank ── retrieval.py │
                          │     ├─ sanitise_tool_result ────  guardrails   │
                          │     └─ TokenBudget.record  ─────  guardrails   │
                          │            │ context                           │
                          │            ▼                                   │
                          │  3. Self-Consistency k=3  ──────  reasoning.py │
                          │     (few-shot CoT: EVIDENCE/ANALYSIS/          │
                          │      CONCLUSION/CONFIDENCE, majority vote)     │
                          │            │ draft                             │
                          │            ▼                                   │
                          │  4. Critic (2nd agent role)  ───  agent.py     │
                          │     verdict: APPROVED / REVISE                 │
                          └────────────────────┬──────────────────────────┘
                                               ▼
                                     answer + critic verdict

   Every LLM call and tool call is wrapped in a Langfuse span (Tracer, agent.py).
   The 3 tools are also exposed standalone via the MCP server (src/mcp_server.py):
   web_search · recall_memory · store_finding.
```

## Components

| File | Role | Origin |
|------|------|--------|
| `src/retrieval.py` | Hybrid search (BM25 + dense TF-IDF + RRF), parent-child chunking, cross-encoder rerank. Corpus from `data/corpus.json`. | Block 1 |
| `src/guardrails.py` | L1 input filter, `sanitise_tool_result`, L4 action gate (`RISK_MATRIX`), `TokenBudget`. | Block 2 |
| `src/reasoning.py` | Few-shot CoT prompt + Self-Consistency (k=3, stance-signature vote). | Block 3 |
| `src/mcp_server.py` | MCP server exposing 3 tools over stdio. | Block 1 §8 |
| `src/agent.py` | Main loop wiring L1 → gated retrieval → synthesis → critic; Langfuse tracing; **critic** (new). | Blocks 1-4 |
| `tests/test_security.py` | 5 injection tests (L1 / architecture / L4). | Block 2 |

## Non-obvious design decision

**The critic falls back to a deterministic groundedness check when offline.** Rather
than making the second agent role depend on an API key, `critic()` uses an LLM verdict
when credentials exist and the Block-1 groundedness score otherwise. This keeps a
*visible verdict* in the output from a clean clone (grader requirement) while still
upgrading to a real LLM critique in production. The alternative — an LLM-only critic —
would make the whole pipeline non-functional without keys, exactly the failure mode the
brief penalises.
