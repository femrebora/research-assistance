#!/usr/bin/env python3
"""Search MCP Server — high-quality web + academic search for pipeline agents.

Provides:
  - search_academic(query) — Semantic Scholar (free, recent papers, citation data)
  - search_web(query)     — multi-backend web search (best available)
  - search_all(query)     — combined academic + web for comprehensive research

Run: python agentic/mcp_servers/search_server.py
Configure in Claude Code: add to .claude/mcp.json
"""
from __future__ import annotations

import os
import sys

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("PaperForge Search")

MAX_RESULTS = 8


# ── Academic Search (Semantic Scholar) ─────────────────────────────────────

def _search_academic(query: str, max_results: int = MAX_RESULTS) -> list[dict]:
    """Search Semantic Scholar for academic papers. Free, no API key."""
    try:
        from semanticscholar import SemanticScholar
        sch = SemanticScholar(timeout=30)
        papers = sch.search_paper(
            query, limit=max_results,
            fields=["title","year","authors","journal","citationCount",
                    "externalIds","abstract","publicationTypes"],
        )

        results = []
        for p in papers:
            authors = getattr(p, "authors", []) or []
            author_names = [a.name for a in authors[:5]]
            journal = getattr(p, "journal", None) or {}
            venue = journal.get("name", "") if isinstance(journal, dict) else ""
            doi = (getattr(p, "externalIds", None) or {}).get("DOI", "")

            results.append({
                "title": getattr(p, "title", "Unknown") or "Unknown",
                "year": getattr(p, "year", None),
                "authors": author_names,
                "venue": venue,
                "citations": getattr(p, "citationCount", 0) or 0,
                "doi": doi,
                "abstract": (getattr(p, "abstract", None) or "")[:400],
                "url": f"https://doi.org/{doi}" if doi else "",
            })
        return results
    except ImportError:
        return [{"error": "semanticscholar not installed. Run: pip install semanticscholar"}]
    except Exception as e:
        return [{"error": str(e)}]


# ── Web Search (multi-backend) ─────────────────────────────────────────────

def _search_web_ddg(query: str, max_results: int = MAX_RESULTS) -> list[dict]:
    """DuckDuckGo search (fallback)."""
    try:
        from ddgs import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")[:300],
                    "source": "duckduckgo",
                })
        return results
    except ImportError:
        return [{"error": "ddgs not installed. Run: pip install ddgs"}]
    except Exception as e:
        return [{"error": str(e)}]


def _search_web_serpapi(query: str, max_results: int = MAX_RESULTS) -> list[dict]:
    """SerpAPI Google search (best quality, needs API key)."""
    api_key = os.getenv("SERPAPI_API_KEY", "")
    if not api_key:
        return [{"error": "SERPAPI_API_KEY not set"}]
    try:
        from serpapi import GoogleSearch
        params = {"q": query, "api_key": api_key, "num": max_results, "engine": "google"}
        search = GoogleSearch(params)
        data = search.get_dict()

        results = []
        for r in data.get("organic_results", [])[:max_results]:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("link", ""),
                "snippet": r.get("snippet", "")[:300],
                "source": "google",
            })
        return results
    except ImportError:
        return [{"error": "serpapi not installed"}]
    except Exception as e:
        return [{"error": str(e)}]


# ── MCP Tools ──────────────────────────────────────────────────────────────

@mcp.tool()
def search_academic(query: str, max_results: int = MAX_RESULTS) -> str:
    """Search Semantic Scholar for academic papers.

    Returns title, year, authors, venue, citations, DOI, and abstract for
    each paper. Covers all fields — biology, medicine, CS, chemistry, etc.
    Best for finding recent (2020+) peer-reviewed research.

    Args:
        query: Search query (e.g., "personalized medicine market trends")
        max_results: Max results (default 8)
    """
    results = _search_academic(query, max_results)
    if not results:
        return "No academic papers found."

    lines = []
    for i, r in enumerate(results, 1):
        if "error" in r:
            lines.append(f"Error: {r['error']}")
            continue
        authors = ", ".join(r.get("authors", [])[:3])
        year = r.get("year", "?")
        venue = f" *{r['venue']}*" if r.get("venue") else ""
        lines.append(
            f"{i}. **{r['title']}** ({year}) — {authors}{venue}\n"
            f"   Cited {r['citations']}x. {r.get('abstract', '')[:250]}\n"
            f"   {r.get('url', '')}"
        )
    return "\n\n".join(lines)


@mcp.tool()
def search_web(query: str, max_results: int = MAX_RESULTS) -> str:
    """Search the web for companies, news, market data, and general information.

    Uses the best available backend (SerpAPI Google if key set, otherwise
    DuckDuckGo). Good for finding companies, funding news, product launches,
    market reports, and clinical trial updates.

    Args:
        query: Search query (e.g., "personalized medicine startups 2025 funding")
        max_results: Max results (default 8)
    """
    # Try best backend first
    results = _search_web_serpapi(query, max_results)
    if results and "error" in results[0]:
        results = _search_web_ddg(query, max_results)

    if not results:
        return "No web results found."
    if "error" in results[0]:
        return f"Search error: {results[0]['error']}"

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. **{r['title']}**\n"
            f"   {r.get('snippet', '')[:300]}\n"
            f"   {r.get('url', '')}"
        )
    return "\n\n".join(lines)


@mcp.tool()
def search_all(query: str, max_results: int = MAX_RESULTS) -> str:
    """Combined academic + web search. Returns both in one call.

    Use this for comprehensive research on a topic — gets both peer-reviewed
    papers and web results (companies, news, market data).

    Args:
        query: Search query
        max_results: Max results per source (default 8)
    """
    academic = _search_academic(query, max_results)
    web = _search_web_serpapi(query, max_results)
    if web and "error" in web[0]:
        web = _search_web_ddg(query, max_results)

    out = ["## Academic Papers\n"]
    for i, r in enumerate(academic[:max_results], 1):
        if "error" in r:
            out.append(f"Error: {r['error']}")
            continue
        authors = ", ".join(r.get("authors", [])[:3])
        out.append(
            f"{i}. **{r['title']}** ({r.get('year','?')}) — {authors}\n"
            f"   Cited {r['citations']}x. {r.get('doi','')}"
        )

    out.append("\n## Web Results\n")
    for i, r in enumerate(web[:max_results], 1):
        if "error" in r:
            out.append(f"Error: {r['error']}")
            continue
        out.append(
            f"{i}. **{r['title']}**\n"
            f"   {r.get('snippet','')[:200]}\n"
            f"   {r.get('url','')}"
        )

    return "\n".join(out)


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("PaperForge Search MCP Server starting...", file=sys.stderr)
    mcp.run()
