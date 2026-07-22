# data/

The retrieval pipeline (`src/retrieval.py`) reads its knowledge base from
**`data/corpus.json`** — a flat JSON object `{ "doc_id": "text", ... }`.

## What ships here

`corpus.json` — **195 passages**, one per Article, extracted from the two source PDFs
in `docs/` by `scripts/build_corpus.py`:
- `gdpr_art_1` … `gdpr_art_99` — Regulation (EU) 2016/679 (GDPR), **final text** (99 articles).
- `aiact_art_1` … `aiact_art_85` (+ lettered ones like `aiact_art_52a`) — EU AI Act.
  ⚠️ Sourced from the **pre-final consolidated** AI Act PDF (article numbering differs
  from the final Regulation 2024/1689, which has 113 renumbered articles). See
  `docs/SOURCES.md` to swap it for the final EUR-Lex text.

`eval_questions.json` — 5 questions with `gold_doc` (real article ids) + `ground_truth`,
for the `hit@k`/MRR proxy and RAGAS. Current baseline with the **simulated** reranker:
**hit@3 = 2/5** — headroom the real cross-encoder (GPU) is meant to close.

## Rebuild the corpus

```bash
pip install pypdf
python scripts/build_corpus.py     # docs/*.pdf → data/corpus.json
```

The script **sanitises** each passage: drops page headers/footers, repairs mojibake,
de-hyphenates line breaks, applies NFKC + invisible-char stripping (same as
`guardrails.l1_filter`), and scans every passage against the lab's `INJECTION_PATTERNS`
(defence in depth against poisoned source documents — currently 0 matches).

Chunking unit = one Article. A `Article N` match is treated as a heading only if
followed by a Title-Case word (not a cross-reference), anchored at Article 1 and
advancing in sequence. Recitals and Annexes are **not** included yet — add them by
extending `split_articles()` if you need them.

## Swapping in different / final documents

1. Put the PDF(s) in `docs/` (keep the same filenames, or edit `DOCUMENTS` in the script).
   Large raw files can go in `data/raw/` (git-ignored).
2. `python scripts/build_corpus.py` — no other change needed; `retrieval.py` reloads
   `corpus.json` on import and rebuilds the parent-child index.
3. Update `eval_questions.json` so `gold_doc` ids match the new corpus.
