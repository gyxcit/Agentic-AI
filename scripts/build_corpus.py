"""build_corpus.py — extract, sanitise and chunk docs/*.pdf into data/corpus.json.

New ingestion code (approved). It reuses the project's security layer: each passage
is normalised (NFKC + invisible-char stripping, same as guardrails.l1_filter) and
scanned against the lab's INJECTION_PATTERNS, so the ingested corpus is *sanitised*
the same way runtime inputs are — defence in depth against poisoned source documents.

Chunking unit = one Article (the citeable, substantive unit for a compliance agent).
A "Article N" match is accepted as a heading only if it is followed by a Title-Case
word (not a cross-reference like "Article 13 of Directive…") and N continues the
sequence from Article 1. Recitals and annexes are intentionally left out for now
(see docs/SOURCES.md / data/README.md to extend).

Run:  python scripts/build_corpus.py
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from guardrails import INJECTION_PATTERNS  # noqa: E402  (reuse the lab's patterns)

DOCS_DIR = ROOT / "docs"
OUT = ROOT / "data" / "corpus.json"

DOCUMENTS = [
    {"prefix": "gdpr", "file": "GDPR_2016-679_EN.pdf",
     "label": "Regulation (EU) 2016/679 (GDPR)"},
    {"prefix": "aiact", "file": "EU_AI_Act_2024-1689_EN.pdf",
     "label": "Regulation (EU) 2024/1689 (AI Act)"},
]

# Words that, when they follow "Article N", indicate a cross-reference (not a heading).
STOP_AFTER = {
    "of", "and", "or", "to", "in", "the", "that", "this", "a", "an", "by", "for",
    "with", "on", "as", "when", "where", "shall", "is", "are", "referred", "point",
    "paragraph", "thereof", "which", "under", "pursuant", "laid", "down", "shall",
    "should", "may", "must", "not", "no", "such", "any", "each", "its", "their",
}


def extract_text(pdf_path: Path) -> str:
    return "\n".join((p.extract_text() or "") for p in PdfReader(str(pdf_path)).pages)


def clean_text(t: str) -> str:
    """Sanitise raw PDF text: drop headers/footers, fix mojibake, de-hyphenate, NFKC."""
    # 1) recurring headers / footers / page markers
    t = re.sub(r"EU General Data Protection Regulation\s*\|?", " ", t)
    t = re.sub(r"Official Journal of the European Union[^\n]*", " ", t)
    t = re.sub(r"\bPage\s+\d+\s+of\s+\d+\b", " ", t)
    # 2) best-effort mojibake repair (typographic quotes decoded as U+FFFD)
    t = t.replace(chr(0xFFFD), "'")
    # 3) same normalisation as guardrails.l1_filter (NFKC + invisible chars)
    t = unicodedata.normalize("NFKC", t)
    t = re.sub(r"[​-‏﻿]", "", t)
    # 4) de-hyphenate words broken across a line break, then collapse whitespace
    t = re.sub(r"(\w)-\s+(\w)", r"\1\2", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _art_key(numstr: str) -> tuple:
    """Sort key for an article label like '28' or '28a' → (28, '') / (28, 'a')."""
    m = re.match(r"(\d+)([a-z]?)", numstr)
    return (int(m.group(1)), m.group(2))


def split_articles(text: str, prefix: str) -> dict:
    """Split cleaned text into {prefix_art_N: passage} using the heading heuristic.

    A 'Article N' match is a heading only if followed by a Title-Case word (not a
    cross-reference). The sequence is anchored at the first real 'Article 1' heading,
    then advances to any strictly-greater label whose numeric part does not jump by
    more than 6 (tolerates a few headings mangled by PDF spacing). Lettered articles
    (e.g. 28a) — used by the pre-final AI Act text — are captured too.
    """
    matches = list(re.finditer(r"\bArticle\s+(\d+[a-z]?)\b", text))
    cands = []
    for m in matches:
        after = text[m.end():m.end() + 40].lstrip()
        first = re.match(r"([A-Za-zÀ-ÿ]+)", after)
        word = first.group(1) if first else ""
        if word and word[0].isupper() and word.lower() not in STOP_AFTER:
            cands.append((m.group(1), m.start()))

    # anchor at the first candidate whose label is exactly "1" (Article 1)
    anchor = next((i for i, (n, _) in enumerate(cands) if n == "1"), None)
    if anchor is None:
        return {}

    accepted = []          # list of (numstr, start_index)
    last = (0, "")
    for numstr, start in cands[anchor:]:
        key = _art_key(numstr)
        if key > last and key[0] <= last[0] + 6:
            accepted.append((numstr, start))
            last = key

    entries = {}
    for j, (numstr, start) in enumerate(accepted):
        end = accepted[j + 1][1] if j + 1 < len(accepted) else len(text)
        passage = text[start:end].strip()
        # strip a trailing CHAPTER/SECTION heading that belongs to the next article
        passage = re.sub(r"\s+(CHAPTER|SECTION)\s+[IVXLC]+\s*[A-Za-z ]*$", "", passage)
        if len(passage.split()) >= 8:
            entries[f"{prefix}_art_{numstr}"] = passage
    return entries


def scan_injections(entries: dict) -> list:
    """Defence-in-depth: report passages matching any injection pattern."""
    flagged = []
    for doc_id, text in entries.items():
        low = text.lower()
        for pattern, name in INJECTION_PATTERNS:
            if re.search(pattern, low):
                flagged.append((doc_id, name))
                break
    return flagged


def main() -> None:
    corpus = {}
    for doc in DOCUMENTS:
        path = DOCS_DIR / doc["file"]
        if not path.exists():
            print(f"⚠  missing {path}; skipping")
            continue
        raw = extract_text(path)
        cleaned = clean_text(raw)
        entries = split_articles(cleaned, doc["prefix"])
        labels = sorted((k.rsplit("_", 1)[1] for k in entries), key=_art_key)
        span = f"{labels[0]}–{labels[-1]}" if labels else "none"
        print(f"{doc['label']:<38} → {len(entries):>3} articles (Art {span})")
        corpus.update(entries)

    flagged = scan_injections(corpus)
    print(f"\nSanitise scan: {len(flagged)} passage(s) matched an injection pattern.")
    for doc_id, name in flagged:
        print(f"   ⚠  {doc_id}: {name}")

    OUT.write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")
    total_words = sum(len(v.split()) for v in corpus.values())
    print(f"\nWrote {OUT.relative_to(ROOT)} — {len(corpus)} passages, ~{total_words:,} words.")
    # show two samples
    for doc_id in list(corpus)[:1] + [k for k in corpus if k == "aiact_art_5"][:1]:
        print(f"\n### {doc_id}\n{corpus[doc_id][:220]}…")


if __name__ == "__main__":
    main()
