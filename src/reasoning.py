"""
reasoning.py — Few-shot CoT (EVIDENCE/ANALYSIS/CONCLUSION/CONFIDENCE) + Self-Consistency k=3.

Code ported from lab_B3_reasoning.ipynb (Block 3):
    SYSTEM_SYNTHESIS (few-shot CoT prompt), answer(), self_consistent_answer().

Only edit vs the notebook: the few-shot example in SYSTEM_SYNTHESIS is adapted to
the project domain (EU AI Act / GDPR governance), exactly as the lab instructs
("TODO: adapt this example to your business domain"). The reasoning format and the
Self-Consistency voting logic are unchanged.
"""
from __future__ import annotations

import re
from collections import Counter

from llm_helpers import make_client, credentials_available

ONLINE = credentials_available()


def demo(script=None):
    return make_client(offline_script=script, quiet=True)


# --------------------------------------------------------------------------- #
# B3 §2 — the answer helper
# --------------------------------------------------------------------------- #
def answer(question, context, system, script=None):
    client = demo(script or [f"[simulated response] {question[:40]}…"])
    msg = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION: {question}"},
    ]
    return client.complete(msg).content


# --------------------------------------------------------------------------- #
# B3 §3 — few-shot CoT prompt (domain example adapted to AI governance)
# --------------------------------------------------------------------------- #
SYSTEM_SYNTHESIS = """
You are a research synthesis agent for AI-governance and regulatory compliance.
Always use this format:

EVIDENCE:
  - [fact 1 with source]
  - [fact 2 with source]

ANALYSIS:
  Step 1: [first reasoning step]
  Step 2: [second reasoning step]
  Step 3: [reconcile any contradictions]

CONCLUSION: [your answer]
CONFIDENCE: HIGH / MEDIUM / LOW — [one-sentence justification]

Example:
Question: Does the EU AI Act impose conformity assessment on a CV-screening tool?
EVIDENCE:
  - EU AI Act Annex III: employment and worker-management AI is high-risk
  - EU AI Act high-risk obligations: conformity assessment required before market placement
ANALYSIS:
  Step 1: CV screening decides access to employment, which Annex III lists as high-risk
  Step 2: High-risk systems must pass a conformity assessment before deployment
  Step 3: No exemption in the context applies to internal recruitment tools
CONCLUSION: Yes — a CV-screening tool is high-risk and requires a conformity assessment
CONFIDENCE: HIGH — Annex III and the high-risk obligations both apply directly
"""


# --------------------------------------------------------------------------- #
# B3 §4 — Self-Consistency (k voices, majority vote on a stance signature)
# --------------------------------------------------------------------------- #
def self_consistent_answer(question: str, context: str, k: int = 3) -> dict:
    """Generate k independent reasoning chains and return the majority answer.

    k = 3 costs 3x the tokens — use for the final synthesis only.
    In offline mode: distinct scripts simulate the diversity of responses.
    """
    mock_scripts = [
        ["EVIDENCE:\n  - Annex III: high-risk\nCONCLUSION: Yes, high-risk.\nCONFIDENCE: HIGH"],
        ["EVIDENCE:\n  - Conformity assessment required\nCONCLUSION: Yes, obligations apply.\nCONFIDENCE: HIGH"],
        ["EVIDENCE:\n  - Human oversight required\nCONCLUSION: Yes.\nCONFIDENCE: MEDIUM"],
    ]

    answers = []
    for i in range(k):
        script = mock_scripts[i % len(mock_scripts)] if not ONLINE else None
        resp = answer(question, context, SYSTEM_SYNTHESIS, script=script)
        m = re.search(r"CONCLUSION\s*:\s*(.+?)(?:\nCONFIDENCE:|$)", resp, re.DOTALL)
        conclusion = m.group(1).strip() if m else resp[-200:]
        answers.append({"conclusion": conclusion, "full": resp})

    def stance_signature(text: str) -> str:
        t = text.lower()
        polarity = "yes" if ("yes" in t[:15] or "high-risk" in t or "required" in t) else "other"
        keywords = sorted(kw for kw in ["annex", "conformity", "gdpr", "high-risk",
                                        "transparency", "oversight"] if kw in t)
        return polarity + "|" + ",".join(keywords[:3])

    signatures = [stance_signature(r["conclusion"]) for r in answers]
    winning_sig, count = Counter(signatures).most_common(1)[0]
    majority = next(r["conclusion"] for r, s in zip(answers, signatures) if s == winning_sig)

    return {
        "answer": majority,
        "confidence": count / k,
        "k": k,
        "agreement": count,
        "all": answers,
    }
