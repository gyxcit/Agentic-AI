# AI-Governance Research Agent — EU AI Act / GDPR compliance

A production research agent that answers AI-governance questions (EU AI Act, GDPR,
cross-jurisdiction comparison) using production-grade retrieval, an injection-tested
guardrail stack, chain-of-thought reasoning with self-consistency, and a critic that
verifies every answer before it is returned.

Built by assembling the four course labs:

- **Block 1** — hybrid search (BM25 + dense + RRF) + cross-encoder reranking + MCP server
- **Block 2** — L1 input filter + L4 action gate + token budget
- **Block 3** — few-shot CoT (EVIDENCE / ANALYSIS / CONCLUSION / CONFIDENCE) + Self-Consistency k=3
- **Block 4** — Langfuse tracing, critic agent, EU AI Act assessment

See `docs/architecture.md` for the component diagram.

## Quickstart (clean clone)

```bash
git clone <your-repo>
cd <your-repo>
cp .env.example .env        # fill in your own keys (or leave empty for offline mock)
pip install -r requirements.txt
python src/agent.py         # runs and prints an answer + critic verdict
```

With **no API key**, the agent runs on the offline `MockLLMClient` (deterministic demo).
Add a key to `.env` and the same code calls the real model — no change needed.

Ask a custom question:

```bash
python src/agent.py "Does the EU AI Act require a conformity assessment for a hiring tool?"
```

## Run the security tests (must be 5/5)

```bash
pytest tests/test_security.py -v
# or, without pytest:
python tests/test_security.py
```

## Run the MCP server (Deliverable: 3 tools)

```bash
pip install mcp requests nest_asyncio
python src/mcp_server.py                                  # stdio server
npx @modelcontextprotocol/inspector python src/mcp_server.py   # visual inspector (needs Node)
```

## Providers — pick one in `.env`

All modes are handled by `src/llm_helpers.py` with **zero code change** — only `.env`
differs. The **default preference is Mistral online**. If no valid key is found, the
agent falls back to an offline mock so the repo still runs.

| Mode | `LLM_PROVIDER` | Key env vars |
|------|----------------|--------------|
| **A) Mistral online (default)** | `mistral` | `MISTRAL_API_KEY`, `LLM_MODEL=mistral-large-latest` |
| B) Downloaded model + GPU (vLLM) | `openai` | `OPENAI_BASE_URL=http://localhost:8000/v1`, `OPENAI_API_KEY=not-needed` |
| C) Ollama | `openai` | `OPENAI_BASE_URL=http://localhost:11434/v1`, `OPENAI_API_KEY=ollama` |
| D) OpenAI / Groq | `openai` | `OPENAI_API_KEY` (+ `OPENAI_BASE_URL` for Groq) |

### A) Mistral online (default)

```
LLM_PROVIDER=mistral
LLM_MODEL=mistral-large-latest      # or mistral-small-latest (cheaper)
MISTRAL_API_KEY=...
```

### B) Downloaded open-source model on a GPU (vLLM)

`llm_helpers.py` speaks the OpenAI protocol, so any OpenAI-compatible local server works.
On a GPU box (e.g. Colab `gpu_colab` kernel):

```bash
pip install vllm
python -m vllm.entrypoints.openai.api_server \
    --model mistralai/Mistral-7B-Instruct-v0.3 --port 8000
```
```
LLM_PROVIDER=openai
LLM_MODEL=mistralai/Mistral-7B-Instruct-v0.3
OPENAI_BASE_URL=http://localhost:8000/v1
OPENAI_API_KEY=not-needed
```

### C) Ollama

```bash
ollama pull mistral
```
```
LLM_PROVIDER=openai
LLM_MODEL=mistral
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama
```

### GPU / real cross-encoder reranker

The default reranker is the simulated one from Block 1 (CPU, no dependency). To use the
real cross-encoder — validate it in Colab first, then:

```bash
pip install -r requirements.txt -r requirements-gpu.txt
export USE_REAL_RERANKER=1          # Windows: set USE_REAL_RERANKER=1
```

`src/retrieval.py` then loads `cross-encoder/ms-marco-MiniLM-L-6-v2` on the GPU.

## Observability (Langfuse)

Set `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` (+ `LANGFUSE_HOST` **or** `LANGFUSE_BASE_URL`)
in `.env`. If unset, tracing is a no-op and the agent still runs (clean-clone safe).

Implemented in `src/observability.py` (Langfuse Python SDK v4, `pip install langfuse`).
Each `run()` produces one trace:

```
ai-governance-agent            (span, trace input=question / output=answer)
├─ retrieve-context            (span)
│  ├─ llm-call                 (generation — model + token usage)
│  ├─ search_knowledge         (retriever)
│  └─ llm-call                 (generation)
├─ synthesize-answer           (chain)
│  └─ llm-call × 3             (generation — Self-Consistency k=3)
└─ critique-answer             (agent — the critic's LLM verdict)
```

Plus three trace-level **scores**: `self_consistency`, `groundedness`, `critic_verdict`.
LLM calls are captured centrally (one `generation` per call, with model name + tokens),
so every provider (Mistral / OpenAI-compatible / mock) is traced with no call-site changes.

## Evaluation (RAGAS)

Install the GPU/eval extras and run RAGAS on `data/eval_questions.json` (baseline vs
final) — see Block 1 §6b for the pinned setup. Record the numbers in `REPORT.md`.

## Repository layout

```
├── README.md · REPORT.md · requirements.txt · requirements-gpu.txt · .env.example
├── src/
│   ├── agent.py         # main loop: L1 → gated retrieval → synthesis → critic (+Langfuse)
│   ├── mcp_server.py    # MCP server, 3 tools
│   ├── retrieval.py     # hybrid search + reranking
│   ├── guardrails.py    # L1 filter + L4 gate + TokenBudget
│   ├── reasoning.py     # few-shot CoT + self-consistency
│   └── llm_helpers.py   # provider-agnostic LLM client (from the labs)
├── tests/test_security.py   # 5 injection tests
├── docs/architecture.md
└── data/                    # corpus.json + eval_questions.json + how to populate
```
