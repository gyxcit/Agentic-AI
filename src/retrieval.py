"""
retrieval.py — Hybrid search (BM25 + dense TF-IDF + RRF) + cross-encoder reranking.

Code ported (near-verbatim) from lab_B1_advanced_rag.ipynb (Block 1):
    _tokenise, TinyTfidf, TinyBM25, rrf_fusion, parent-child chunking,
    cross_encoder_score (simulated), rerank, production_retrieve, search_knowledge.

Differences vs the notebook (kept minimal and documented):
  1. CORPUS is loaded from ../data/corpus.json (topic: AI governance) instead of
     being hard-coded in a cell. Same dict shape {doc_id: text}.
  2. An OPTIONAL real cross-encoder hook (sentence-transformers) is scaffolded but
     DISABLED by default. Validate it in Colab first, then set USE_REAL_RERANKER=1
     (see README "GPU / real reranker"). Until then the simulated scorer from the
     lab is used, so the repo runs from a clean clone with no GPU.
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from pathlib import Path

# --------------------------------------------------------------------------- #
# Corpus loading (data/corpus.json)
# --------------------------------------------------------------------------- #
_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "corpus.json"


def load_corpus() -> dict:
    """Load the {doc_id: text} corpus. Falls back to {} if the file is missing."""
    if _DATA_FILE.exists():
        return json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    return {}


CORPUS = load_corpus()


# --------------------------------------------------------------------------- #
# B1 §1 — tokeniser
# --------------------------------------------------------------------------- #
def _tokenise(text):
    return re.findall(r"[a-zàâçéèêëîïôûùüÿœ0-9]+", text.lower())


# --------------------------------------------------------------------------- #
# B1 §1 — TinyTfidf (dense retriever)
# --------------------------------------------------------------------------- #
class TinyTfidf:
    "Minimal TF-IDF retriever (cosine), no external dependency."

    def __init__(self, docs: dict):
        self.names = list(docs.keys())
        self.texts = list(docs.values())
        tok = [_tokenise(t) for t in self.texts]
        N = len(self.texts)
        df = Counter(w for ts in tok for w in set(ts))
        self.idf = {w: math.log((1 + N) / (1 + df[w])) + 1 for w in df}
        self.vecs = [self._vec(ts) for ts in tok]

    def _vec(self, tokens):
        tf = Counter(tokens)
        n = len(tokens) or 1
        return {w: tf[w] / n * self.idf.get(w, 0.0) for w in tf}

    @staticmethod
    def _cos(a, b):
        num = sum(a[w] * b[w] for w in set(a) & set(b))
        na = math.sqrt(sum(v ** 2 for v in a.values()))
        nb = math.sqrt(sum(v ** 2 for v in b.values()))
        return num / (na * nb) if na * nb else 0.0

    def search(self, query: str, k: int = 3) -> list:
        qv = self._vec(_tokenise(query))
        scores = [(self._cos(qv, v), t) for v, t in zip(self.vecs, self.texts)]
        return sorted(scores, reverse=True)[:k]


# --------------------------------------------------------------------------- #
# B1 §4 — TinyBM25 (lexical retriever)
# --------------------------------------------------------------------------- #
class TinyBM25:
    "Minimal BM25-Okapi, no external dependency."

    def __init__(self, docs: dict, k1: float = 1.5, b: float = 0.75):
        self.names = list(docs.keys())
        self.texts = list(docs.values())
        self.tok = [_tokenise(t) for t in self.texts]
        N = len(self.texts)
        avgdl = sum(len(ts) for ts in self.tok) / N if N else 0
        df = Counter(w for ts in self.tok for w in set(ts))
        self.idf = {w: math.log((N - df[w] + 0.5) / (df[w] + 0.5) + 1) for w in df}
        self._k1 = k1
        self._b = b
        self._avgdl = avgdl

    def _score(self, tok_q, idx):
        dl = len(self.tok[idx])
        sc = 0.0
        tf_d = Counter(self.tok[idx])
        for w in tok_q:
            if w not in self.idf:
                continue
            f = tf_d[w]
            num = self.idf[w] * f * (self._k1 + 1)
            den = f + self._k1 * (1 - self._b + self._b * dl / self._avgdl)
            sc += num / den
        return sc

    def search(self, query: str, k: int = 3) -> list:
        q = _tokenise(query)
        ranked = sorted(range(len(self.texts)),
                        key=lambda i: self._score(q, i), reverse=True)
        return [(self._score(q, i), self.texts[i]) for i in ranked[:k]]


# --------------------------------------------------------------------------- #
# B1 §4 — Reciprocal Rank Fusion
# --------------------------------------------------------------------------- #
def rrf_fusion(lists: list, K: int = 60) -> list:
    """Reciprocal Rank Fusion — fuses several lists of (score, text)."""
    scores = {}
    for lst in lists:
        for rank, (_, text) in enumerate(lst):
            scores[text] = scores.get(text, 0.0) + 1.0 / (K + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# --------------------------------------------------------------------------- #
# B1 §3 — Parent-child chunking (retrieve small, return large)
# --------------------------------------------------------------------------- #
def split_words(text: str, size: int, overlap: int) -> list:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i:i + size]))
        i += size - overlap
    return chunks


children: dict = {}          # chunk_id -> short text
parents: dict = {}           # chunk_id -> long text
child_to_parent: dict = {}

for _doc_id, _text in CORPUS.items():
    for _p_idx, _parent_text in enumerate(split_words(_text, size=80, overlap=10)):
        _parent_id = f"{_doc_id}_p{_p_idx}"
        parents[_parent_id] = _parent_text
        for _c_idx, _child_text in enumerate(split_words(_parent_text, size=20, overlap=3)):
            _child_id = f"{_parent_id}_c{_c_idx}"
            children[_child_id] = _child_text
            child_to_parent[_child_id] = _parent_id

retriever_children = TinyTfidf(children) if children else None


# --------------------------------------------------------------------------- #
# B1 §5 — Cross-encoder reranking
# --------------------------------------------------------------------------- #
def cross_encoder_score(query: str, document: str) -> float:
    """
    Simulated cross-encoder — in production: sentence_transformers.CrossEncoder.
    Approximates relevance by combining term coverage and shared length.
    """
    q_tok = set(_tokenise(query))
    d_tok = set(_tokenise(document))
    if not q_tok or not d_tok:
        return 0.0
    overlap = len(q_tok & d_tok) / len(q_tok)
    doc_bonus = min(1.0, len(d_tok) / 50)
    return round(overlap * 0.7 + doc_bonus * 0.3, 4)


# --- OPTIONAL real cross-encoder (GPU). DISABLED by default. ---------------- #
# Validate this in Colab first (see README, "GPU / real reranker"), then set
# USE_REAL_RERANKER=1 in your environment. Kept lazy + guarded so a clean clone
# without sentence-transformers/torch still runs on the simulated scorer above.
_REAL_RERANKER = None


def _get_real_reranker():
    global _REAL_RERANKER
    if _REAL_RERANKER is None:
        from sentence_transformers import CrossEncoder  # heavy import, GPU-friendly
        model_name = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
        _REAL_RERANKER = CrossEncoder(model_name)
    return _REAL_RERANKER


def rerank(query: str, candidates: list, top_k: int = 3) -> list:
    """Rerank `candidates` by cross-relevance with the query."""
    if os.getenv("USE_REAL_RERANKER") == "1":
        model = _get_real_reranker()
        scores = model.predict([(query, doc) for doc in candidates])
        ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
        return [doc for _, doc in ranked[:top_k]]
    scored = [(cross_encoder_score(query, doc), doc) for doc in candidates]
    return [doc for _, doc in sorted(scored, reverse=True)[:top_k]]


# --------------------------------------------------------------------------- #
# B1 §5 — Full production pipeline: hybrid -> parent-child -> rerank
# --------------------------------------------------------------------------- #
def production_retrieve(query: str, k_final: int = 3) -> list:
    """Full pipeline: hybrid (dense+BM25+RRF) over children -> parents -> rerank."""
    if retriever_children is None:
        return []
    # 1. Hybrid over children
    dense_c = retriever_children.search(query, k=10)
    bm25_c = TinyBM25(children).search(query, k=10)
    fused_c = rrf_fusion([dense_c, bm25_c])
    # 2. Go back up to parents
    seen, candidates = set(), []
    for text, _ in fused_c:
        child_id = next((cid for cid, ct in children.items() if ct == text), None)
        if child_id:
            pid = child_to_parent[child_id]
            if pid not in seen:
                seen.add(pid)
                candidates.append(parents[pid])
    # 3. Rerank
    return rerank(query, candidates, top_k=k_final)


# --------------------------------------------------------------------------- #
# B1 §7 — the retriever exposed as an agent tool
# --------------------------------------------------------------------------- #
def search_knowledge(query: str) -> str:
    "Search the internal document base for relevant passages."
    results = production_retrieve(query, k_final=3)
    if not results:
        return "No results found."
    return "\n---\n".join(results)


if __name__ == "__main__":
    q = "What must providers of high-risk AI systems put in place?"
    print(f"Query: {q!r}\n")
    for i, doc in enumerate(production_retrieve(q), 1):
        print(f"[{i}] {doc[:120]}…")
