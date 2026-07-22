"""
observability.py — Langfuse tracing (Python SDK v4), following the Langfuse skill's
best practices. No-op when LANGFUSE_* keys are absent, so the app still runs from a
clean clone.

What it gives every agent run:
  - a root `span` (trace) whose input/output is the question / final answer
  - one `generation` per LLM call, with model name + input messages + token usage
    (monkey-patched onto llm_helpers so ALL callers — retrieval loop, the k=3
    self-consistency voices, and the critic — are captured with no call-site changes)
  - specific observation types: `retriever` for tool lookups, `chain` for the
    synthesis, `agent` for the critic
  - trace-level scores: self-consistency agreement, groundedness, critic verdict

Docs used: langfuse.com/docs/observability/best-practices and .../sdk/instrumentation
(fetched fresh — the Langfuse skill forbids implementing observability from memory).
"""
from __future__ import annotations

import os
from contextlib import nullcontext

# The SDK reads LANGFUSE_HOST; the project's .env may use LANGFUSE_BASE_URL.
if os.getenv("LANGFUSE_BASE_URL") and not os.getenv("LANGFUSE_HOST"):
    os.environ["LANGFUSE_HOST"] = os.environ["LANGFUSE_BASE_URL"]

_client = None
_patched = False


def get_client():
    """Return a cached Langfuse client, or None if keys are missing / init fails."""
    global _client
    if _client is None and os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        try:
            from langfuse import get_client as _gc
            _client = _gc()
        except Exception as exc:  # pragma: no cover
            print(f"[langfuse] disabled ({exc}); running without tracing.")
            _client = None
    return _client


def enabled() -> bool:
    return get_client() is not None


def observation(name: str, as_type: str = "span", **kw):
    """Return Langfuse's native observation context manager (or a no-op).

    Returned directly — NOT wrapped in a @contextmanager generator — so the SDK's
    OpenTelemetry context propagates and child observations (e.g. the LLM
    generations) nest correctly under the active phase.
    """
    lf = get_client()
    if lf is None:
        return nullcontext(None)
    try:
        return lf.start_as_current_observation(name=name, as_type=as_type, **kw)
    except Exception:
        return nullcontext(None)


def instrument_llm_clients() -> None:
    """Monkey-patch complete() on both LLM clients to emit a `generation` per call.

    Single instrumentation point → every LLM call in the app is captured with model
    name, input messages and token usage, and nests under whatever phase span is
    active. Idempotent; only patches when Langfuse is enabled.
    """
    global _patched
    if _patched or not enabled():
        return
    from llm_helpers import LLMClient, MockLLMClient
    lf = get_client()

    for cls in (LLMClient, MockLLMClient):
        original = cls.complete

        def wrapped(self, messages, tools=None, temperature=0.0, max_tokens=1024,
                    tool_choice=None, __orig=original):
            with lf.start_as_current_observation(
                name="llm-call",
                as_type="generation",
                model=getattr(self, "model", "unknown"),
                input=messages,
                model_parameters={"temperature": temperature, "max_tokens": max_tokens},
            ) as gen:
                reply = __orig(self, messages, tools=tools, temperature=temperature,
                               max_tokens=max_tokens, tool_choice=tool_choice)
                u = reply.usage or {}
                out = reply.content or (
                    [{"name": tc["name"], "arguments": tc["arguments"]}
                     for tc in reply.tool_calls] or None)
                try:
                    gen.update(output=out, usage_details={
                        "input": u.get("input_tokens", 0),
                        "output": u.get("output_tokens", 0),
                    })
                except Exception:
                    pass
                return reply

        cls.complete = wrapped
    _patched = True


def set_trace_io(input=None, output=None) -> None:
    lf = get_client()
    if lf is None:
        return
    try:
        lf.set_current_trace_io(input=input, output=output)
    except Exception:
        pass


def score(name: str, value, data_type: str = "NUMERIC", comment: str | None = None) -> None:
    lf = get_client()
    if lf is None:
        return
    try:
        lf.score_current_trace(name=name, value=value, data_type=data_type, comment=comment)
    except Exception:
        pass


def trace_url() -> str | None:
    lf = get_client()
    if lf is None:
        return None
    try:
        return lf.get_trace_url()
    except Exception:
        return None


def flush() -> None:
    lf = get_client()
    if lf is not None:
        try:
            lf.flush()
        except Exception:
            pass
