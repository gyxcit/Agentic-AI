# ✅ My tasks — Production AI Agent (Topic 8: AI governance)

> Deadline: **Thursday July 23, 23:59**. Commits after that are not counted.
> Everything below is what *I* (the student) still have to do. The code structure
> is already built and runs offline. See `README.md` / `docs/architecture.md`.

---

## 0. Already done (by the setup)
- [x] Repo structure conforms to the brief (`src/`, `tests/`, `docs/`, `data/`)
- [x] `retrieval.py` (Block 1), `guardrails.py` (Block 2), `reasoning.py` (Block 3), `mcp_server.py`
- [x] `agent.py` wires L1 → gated retrieval → Self-Consistency k=3 → critic, with Langfuse spans
- [x] Critic agent (2nd role) — visible verdict, offline fallback
- [x] `tests/test_security.py` → **5/5 injection tests pass**
- [x] Seed corpus `data/corpus.json` (EU AI Act + GDPR) + `eval_questions.json`
- [x] Runs from clean clone offline: `python src/agent.py`

---

## 1. Corpus — use the real regulatory texts  🔴 important
- [x] PDFs in `docs/`: `GDPR_2016-679_EN.pdf` (77 p, **final**) + `EU_AI_Act_2024-1689_EN.pdf` (258 p)
- [x] Extracted + sanitised into `data/corpus.json` via `scripts/build_corpus.py`
      → **195 passages** (GDPR art 1–99 + AI Act art 1–85). `eval_questions.json` updated.
      Baseline **hit@3 = 2/5** with the simulated reranker.
- [ ] 🔴 **Swap the AI Act PDF for the FINAL text** (current one is pre-final: art ≤85 + lettered,
      wrong numbering vs Reg. 2024/1689's 113 articles). EUR-Lex is blocked from CLI — do it in a
      browser, then re-run the extractor:
      `! start "" "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=OJ:L_202401689"`
      → save as `docs/EU_AI_Act_2024-1689_EN.pdf`, then `python scripts/build_corpus.py`.
- [ ] (optional) Add Recitals / Annex III to the corpus (extend `split_articles()`).

## 2. Run online / on Colab GPU (needs a key or local Mistral)  🔴
- [ ] Choose the provider in `.env` — **default: Mistral online** (`LLM_PROVIDER=mistral` +
      `MISTRAL_API_KEY`). Alternatives: downloaded model on GPU (vLLM), Ollama, OpenAI/Groq.
      All work with no code change (README "Providers"). Switching verified: mistral / mock / openai-base_url.
- [ ] Validate the **real cross-encoder** in Colab (`USE_REAL_RERANKER=1`), then freeze the version
- [ ] Run **RAGAS baseline (TF-IDF) vs final (hybrid+rerank)** on `eval_questions.json`
      → fill the table in `REPORT.md` §3
- [ ] Measure over 10 runs: avg cost (USD), avg latency (s), tool-call distribution → `REPORT.md` §3

## 3. Observability
- [x] Langfuse tracing implemented (`src/observability.py`, SDK **v4**, best practices).
      Every run = 1 root `span` → `retrieve-context` (generations + `retriever` tool) →
      `synthesize-answer` `chain` (k=3 generations) → `critique-answer` `agent`, + 3
      trace scores (self_consistency, groundedness, critic_verdict). **9+ observations/run.**
      No-op without keys. Keys already in `.env`. Verified trace nesting via REST audit.
- [ ] Capture a **real** trace (real model + token/cost) for the report screenshot.
      Blocked now by the free **Mistral 429 rate limit** — use Ollama/vLLM on Colab GPU
      (no limit) or a paid tier, then re-run `python src/agent.py "<question>"`.
- [ ] (security) **Rotate the Mistral API key** — it was exposed in a chat session.

## 4. REPORT.md — fill every `TODO`  🔴
- [ ] §1 Problem statement: concrete user + scenario (not "help people learn about AI Act")
- [ ] §2 Architecture: confirm diagram matches code; keep the non-obvious design decision
- [ ] §3 RAGAS table + cost/latency/tool numbers
- [ ] §4 Security: before/after table + explain one real block
- [ ] §5 EU AI Act tier (LIMITED RISK) + how the transparency obligation is implemented
- [ ] §6 Limitations + next sprint (be specific)
- [ ] §7 AI use disclosure table (honest)

## 5. MCP deliverable
- [ ] `pip install mcp requests nest_asyncio`
- [ ] `python src/mcp_server.py` runs; verify 3/3 tools (Inspector or the Block-1 §8.3 test)

## 6. Submission
- [ ] Group registered on the topic (first-come-first-served)
- [ ] Push everything to `main` before the deadline
- [ ] Email repo URL to instructor, subject: `[PGE5 HW] Group N — AI governance`

---

### Notes / decisions
- Provider default: **Mistral online API**. Fallbacks: GPU model via vLLM, Ollama, OpenAI/Groq — all env-only, no code change.
- Reranker: simulated by default; real cross-encoder behind `USE_REAL_RERANKER=1` (GPU).
- Ask before adding any code beyond the labs (critic + Langfuse were already approved).
