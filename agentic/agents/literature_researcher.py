"""Literature Researcher agent — hybrid academic + web research.

Combines two research sources:
1. OpenAlex (free academic database, no API key) — like the existing discover.py
2. DuckDuckGo — for companies, market data, clinical applications

Replaces Code Analyst for review articles. Compiles findings into a structured
technical report for the Writer.
"""
from __future__ import annotations

import json
import sys
from urllib.parse import quote
from urllib.request import Request, urlopen

from agentic.bridge import call_agent

MAX_ACADEMIC = 8
MAX_WEB = 6

SYSTEM = """You are a literature research assistant specializing in academic review articles. You synthesize web and academic search results into structured, well-cited research reports.

For each finding, include the source URL so citations can be traced. Organize by:
1. Key methods and breakthroughs (from academic literature)
2. Companies and commercialization (from web search)
3. Market trends and data
4. Clinical applications
5. Future directions

Be specific — include company names, funding amounts, publication venues, DOIs, market sizes, and timelines. Write in note-taking style suitable for a Writer agent to convert into academic prose."""


def _search_semantic_scholar(topic: str, max_results: int = MAX_ACADEMIC) -> str:
    """Search Semantic Scholar for academic papers. Free, no API key needed.

    Better quality results than OpenAlex — includes citation counts, influential
    citations, and publication venues. Focuses on recent (2020+) papers.
    """
    try:
        from semanticscholar import SemanticScholar
        sch = SemanticScholar(timeout=30)
        papers = sch.search_paper(topic, limit=max_results,
                                   fields=["title","year","authors","journal",
                                           "citationCount","externalIds","abstract"])

        results = []
        for p in papers:
            title = getattr(p, "title", "Unknown") or "Unknown"
            year = getattr(p, "year", None) or "?"
            cited = getattr(p, "citationCount", 0) or 0
            authors = getattr(p, "authors", []) or []
            first_author = authors[0].name if authors else ""
            journal = (getattr(p, "journal", None) or {})
            venue = (journal.get("name", "") if isinstance(journal, dict) else str(journal)) if journal else ""
            doi = (getattr(p, "externalIds", None) or {}).get("DOI", "")
            doi_url = f"https://doi.org/{doi}" if doi else ""
            abstract = getattr(p, "abstract", "") or ""
            abstract = abstract[:300] if abstract else ""

            author_str = f"{first_author} et al." if first_author and len(authors) > 1 else first_author
            venue_str = f" *{venue}*" if venue else ""

            results.append(
                f"- **{title}** ({year}) — {author_str}{venue_str}\n"
                f"  Cited {cited}x. {abstract}{'...' if len(abstract) >= 300 else ''}\n"
                f"  {doi_url if doi_url else ''}"
            )

        return "\n".join(results) if results else "(No academic papers found)"
    except ImportError:
        return "(Semantic Scholar library not installed)"
    except Exception as e:
        return f"(Semantic Scholar error: {e})"


def _search_openalex(topic: str, max_results: int = MAX_ACADEMIC) -> str:
    """Fallback: Search OpenAlex if Semantic Scholar fails."""
    try:
        params = f"search={quote(topic)}&sort=cited_by_count:desc&per_page={max_results}"
        url = f"https://api.openalex.org/works?{params}"
        req = Request(url, headers={"User-Agent": "PaperForge/1.0 (mailto:research@example.com)"})
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = []
        for work in data.get("results", []):
            title = work.get("title", "Unknown")
            doi = work.get("doi", "")
            year = work.get("publication_year", "?")
            cited = work.get("cited_by_count", 0)
            results.append(
                f"- **{title}** ({year}) — Cited {cited}x.\n"
                f"  DOI: https://doi.org/{doi}" if doi else f"- **{title}** ({year})"
            )

        return "\n".join(results) if results else "(No academic papers found)"
    except Exception as e:
        return f"(OpenAlex error: {e})"


def _search_web(query: str, max_results: int = MAX_WEB) -> str:
    """Search web using Brave (best) or DuckDuckGo (fallback)."""
    import os

    # Try Brave Search API first
    api_key = os.getenv("BRAVE_API_KEY", "")
    if api_key:
        try:
            import gzip
            import json as _json
            from urllib.parse import quote
            from urllib.request import Request, urlopen

            params = f"q={quote(query)}&count={max_results}"
            req = Request(
                f"https://api.search.brave.com/res/v1/web/search?{params}",
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": api_key,
                },
            )
            with urlopen(req, timeout=15) as resp:
                raw = resp.read()
                if raw[:2] == b'\x1f\x8b':
                    raw = gzip.decompress(raw)
                data = _json.loads(raw.decode("utf-8"))

            results = []
            for r in (data.get("web", {}).get("results", []) or [])[:max_results]:
                results.append(
                    f"- **{r.get('title', '')}**\n"
                    f"  {r.get('description', '')[:300]}\n"
                    f"  URL: {r.get('url', '')}"
                )
            if results:
                return "\n".join(results)
        except Exception:
            pass  # Fall through to DDG

    # DuckDuckGo fallback
    try:
        from ddgs import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(
                    f"- **{r.get('title', '')}**\n"
                    f"  {r.get('body', '')[:300]}\n"
                    f"  URL: {r.get('href', '')}"
                )
        return "\n".join(results) if results else f"(No results for: {query})"
    except Exception as e:
        return f"(Web search error: {e})"


def _gather_research(topic: str) -> str:
    """Run academic + web searches on different aspects of the topic."""
    sections = []

    # 1. Academic literature via Semantic Scholar (primary) or OpenAlex (fallback)
    print("  [Research] Semantic Scholar: searching academic papers...", file=sys.stderr)
    academic = _search_semantic_scholar(topic)
    if academic.startswith("(Semantic Scholar"):
        academic = _search_openalex(topic)
    sections.append(f"## Academic Literature\n\n{academic}\n")

    # 2-5. Web searches for companies, market, clinical
    web_queries = [
        (f"{topic} companies startups commercialization funding 2025 2026", "## Companies & Commercialization"),
        (f"{topic} market size trends growth forecast 2026", "## Market Trends & Data"),
        (f"{topic} clinical applications regulatory milestones FDA", "## Clinical Applications"),
        (f"{topic} future directions challenges opportunities", "## Future Directions"),
    ]

    for query, heading in web_queries:
        print(f"  [Research] Web: {query[:60]}...", file=sys.stderr)
        sections.append(f"{heading}\n\n{_search_web(query)}\n")

    return "\n".join(sections)


def run_literature_researcher(state: dict) -> dict:
    """Search academic DBs + web, then synthesize into a technical report."""
    topic = state.get("research_topic") or state.get("user_summary", "")

    print(f"  [Research] Gathering research on: {topic[:80]}", file=sys.stderr)

    research_data = _gather_research(topic)

    print(f"  [Research] Synthesizing {len(research_data)} chars into technical report...", file=sys.stderr)

    prompt = f"""Synthesize the following research into a structured technical report for an academic review article.

## Research Topic
{topic}

## Research Data
{research_data}

## Your Task

Compile a comprehensive technical report covering:
1. **Introduction/Background** — state of the field, why this matters now
2. **Key Methods & Breakthroughs** — recent advances (2024-2026) with specific names, publications, and capabilities
3. **Companies & Commercialization** — startups, funding, products, partnerships
4. **Market Trends** — market sizes, growth rates, key segments
5. **Clinical Applications** — real-world impact, regulatory milestones
6. **Future Directions** — emerging trends, challenges, opportunities

Format in Markdown with ## section headings. Include source URLs and DOIs inline. Be specific with numbers, names, and dates. This report will be used by a Writer agent to produce a complete academic review article."""

    result = call_agent(prompt=prompt, model="claude", system=SYSTEM, temperature=0.3)

    return {
        "technical_report": result["text"],
        "agent_calls": [{
            "agent": "literature_researcher",
            "model": "claude",
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "cost": result["cost"],
        }],
    }
