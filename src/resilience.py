"""
resilience.py — retry-with-backoff on rate-limit (HTTP 429) for LLM calls.

New code (approved, non-lab). The agent fires ~5-7 LLM calls in quick succession
(retrieval + k=3 self-consistency + critic), which can trip a provider's per-second
rate limit (observed: Mistral 429 "rate_limited"). This wraps LLMClient.complete to
retry on 429 with exponential backoff + jitter, so bursts succeed instead of failing.

Applied via monkey-patch (like observability.py) so the lab files stay untouched.
Only the real client is wrapped — the mock never rate-limits.

Tunable via env:  LLM_MAX_RETRIES (default 5), LLM_RETRY_BASE_DELAY (default 0.7s).
"""
from __future__ import annotations

import os
import random
import time

_patched = False
_MAX_ATTEMPTS = int(os.getenv("LLM_MAX_RETRIES", "5"))
_BASE_DELAY = float(os.getenv("LLM_RETRY_BASE_DELAY", "0.7"))


def _is_rate_limit(exc: Exception) -> bool:
    """True if the exception looks like a 429 / rate-limit, across SDKs."""
    for attr in ("status_code", "http_status", "code"):
        if getattr(exc, attr, None) in (429, "429"):
            return True
    s = str(exc).lower()
    return ("429" in s or "rate limit" in s or "rate_limited" in s
            or "too many requests" in s)


def instrument_retries() -> None:
    """Monkey-patch LLMClient.complete to retry on rate-limit errors. Idempotent."""
    global _patched
    if _patched:
        return
    from llm_helpers import LLMClient

    original = LLMClient.complete

    def wrapped(self, messages, tools=None, temperature=0.0, max_tokens=1024,
                tool_choice=None, __orig=original):
        delay = _BASE_DELAY
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                return __orig(self, messages, tools=tools, temperature=temperature,
                              max_tokens=max_tokens, tool_choice=tool_choice)
            except Exception as exc:
                if attempt == _MAX_ATTEMPTS or not _is_rate_limit(exc):
                    raise
                wait = delay + random.uniform(0, 0.3)   # jitter avoids thundering herd
                print(f"[retry] rate-limited (429) — attempt {attempt}/{_MAX_ATTEMPTS}, "
                      f"waiting {wait:.1f}s")
                time.sleep(wait)
                delay *= 2

    LLMClient.complete = wrapped
    _patched = True
