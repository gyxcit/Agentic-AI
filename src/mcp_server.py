"""mcp_server.py — a 3-tool MCP server for AI-governance / EU AI Act research.

Code ported verbatim from lab_B1_advanced_rag.ipynb (Block 1, §8.2). The three
tools (web_search, recall_memory, store_finding) and their docstring patterns are
unchanged; only the embedded CORPUS is adapted to the project domain so the server
answers governance questions offline.

Run standalone:  python src/mcp_server.py
Inspect:         npx @modelcontextprotocol/inspector python src/mcp_server.py
"""
from mcp.server.fastmcp import FastMCP
import requests

mcp = FastMCP("research-tools")

# ── A tiny local corpus so recall_memory works offline ──
CORPUS = {
    "aiact_risk_tiers": "The EU AI Act classifies AI systems into four risk tiers: "
                        "unacceptable (prohibited), high, limited, and minimal risk.",
    "aiact_high_risk": "High-risk AI systems must implement a risk management system, "
                       "data governance, technical documentation, logging, human oversight, "
                       "and a conformity assessment before market placement.",
    "aiact_transparency": "Limited-risk AI systems must inform users they interact with an "
                          "AI, and AI-generated deepfake content must be labelled.",
    "gdpr_article22": "GDPR Article 22 gives individuals the right not to be subject to a "
                      "decision based solely on automated processing that significantly affects them.",
    "gdpr_fines": "GDPR infringements can lead to fines up to 20 million euros or 4% of "
                  "worldwide annual turnover, whichever is higher.",
}
# In-memory store for findings saved during a session
_STORE = {}


@mcp.tool()
def web_search(query: str, num_results: int = 3) -> str:
    """Search the public web for current information.

    Use when: you need facts, news or citations that are NOT already in memory.
    Do NOT use for: maths, or a topic you already saved with store_finding.
    Returns: a numbered list of results, each with a title and a snippet.
    Example: query="EU AI Act general-purpose AI obligations 2025"
    """
    try:
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        topics = data.get("RelatedTopics", [])
        results = []
        for t in topics[:num_results]:
            if isinstance(t, dict) and t.get("Text"):
                results.append(t["Text"])
        if not results:
            abstract = data.get("AbstractText", "")
            return abstract or "No results found. Try a broader query or use recall_memory."
        return "\n".join(f"{i+1}. {txt}" for i, txt in enumerate(results))
    except requests.Timeout:
        return "Search timed out. Try recall_memory instead."
    except Exception as e:
        return f"Search error: {e}. Try recall_memory instead."


@mcp.tool()
def recall_memory(query: str) -> str:
    """Retrieve relevant passages from the internal knowledge base.

    Use FIRST, before web_search — it is free and instant.
    Returns: matching passages with their source id, or a message to try web_search.
    Example: query="what obligations apply to high-risk AI"
    """
    try:
        q = set(query.lower().split())
        scored = []
        for doc_id, text in {**CORPUS, **_STORE}.items():
            overlap = len(q & set(text.lower().split()))
            if overlap:
                scored.append((overlap, doc_id, text))
        scored.sort(reverse=True)
        if not scored:
            return "No relevant memories. Use web_search to find new information."
        return "\n---\n".join(f"[{doc_id}] {text}" for _, doc_id, text in scored[:3])
    except Exception as e:
        return f"Recall error: {e}"


@mcp.tool()
def store_finding(finding: str, source: str) -> str:
    """Save a verified finding to memory so recall_memory can return it later.

    Use after web_search when you find a credible, relevant fact.
    Do NOT store: speculation or unverified claims.
    Returns: a confirmation string.
    Example: finding="GPAI systemic-risk threshold is 10^25 FLOPs", source="EU AI Act"
    """
    try:
        key = f"finding_{len(_STORE) + 1}"
        _STORE[key] = f"{finding} (source: {source})"
        return f"Stored as {key}: {_STORE[key]}"
    except Exception as e:
        return f"Store error: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
