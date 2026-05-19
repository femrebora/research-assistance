#!/usr/bin/env python3
"""discover.py — find new papers from external sources to import into Zotero.

Searches OpenAlex (no key needed), Semantic Scholar (optional key), and
Elicit (requires ELICIT_API_KEY) for papers matching a query. Useful when
the answer to "what should I read next?" is NOT in your current library.

By default, OpenAlex is used because it requires no API key and has the
broadest coverage. Use --source to switch.

Usage:
    ./discover.py "NUMT contamination clinical mtDNA" --limit 15
    ./discover.py "..." --source semantic_scholar --year-from 2020
    ./discover.py "..." --source elicit --question
    ./discover.py "..." --export bibtex > new_papers.bib
    ./discover.py "..." --json
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

import click
import httpx
from rich.console import Console
from rich.table import Table

console = Console()

OPENALEX_URL = "https://api.openalex.org/works"
SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
ELICIT_URL = "https://api.elicit.com/v1/searches"

USER_AGENT = "Research-Assistance/0.2 (mailto:researcher@example.com)"
HTTP_TIMEOUT = 30.0


@dataclass(frozen=True)
class Paper:
    title: str
    authors: tuple[str, ...]
    year: Optional[int]
    venue: str = ""
    doi: str = ""
    url: str = ""
    abstract: str = ""
    citation_count: int = 0
    source: str = ""

    @property
    def first_author_last(self) -> str:
        if not self.authors:
            return ""
        full = self.authors[0].strip()
        return full.split()[-1] if full else ""

    @property
    def suggested_citekey(self) -> str:
        last = self.first_author_last.lower()
        last = "".join(c for c in last if c.isalnum())
        year = str(self.year) if self.year else "nd"
        first_title_word = ""
        for w in self.title.split():
            cleaned = "".join(c for c in w.lower() if c.isalnum())
            if len(cleaned) >= 4 and cleaned not in {"the", "and", "with", "from", "into", "this", "that", "what", "when"}:
                first_title_word = cleaned
                break
        return f"{last}{year}{first_title_word}" if last else f"unknown{year}"


# ── OpenAlex ─────────────────────────────────────────────────────────────────

def _abstract_from_inverted(inv: Optional[dict]) -> str:
    """OpenAlex serves abstracts as a token→positions inverted index. Reconstruct."""
    if not inv:
        return ""
    positions = []
    for token, idxs in inv.items():
        for i in idxs:
            positions.append((i, token))
    positions.sort()
    return " ".join(tok for _, tok in positions)


def search_openalex(query: str, limit: int = 20, year_from: Optional[int] = None) -> list[Paper]:
    params = {
        "search": query,
        "per-page": min(limit, 50),
        "select": "id,doi,title,publication_year,authorships,primary_location,cited_by_count,abstract_inverted_index",
    }
    if year_from:
        params["filter"] = f"from_publication_date:{year_from}-01-01"

    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(timeout=HTTP_TIMEOUT, headers=headers) as client:
        r = client.get(OPENALEX_URL, params=params)
        r.raise_for_status()
        data = r.json()

    out: list[Paper] = []
    for w in data.get("results", []):
        authors = tuple(
            a.get("author", {}).get("display_name", "")
            for a in w.get("authorships", [])
            if a.get("author")
        )
        primary = w.get("primary_location") or {}
        venue = (primary.get("source") or {}).get("display_name", "") or ""
        doi = (w.get("doi") or "").replace("https://doi.org/", "")
        out.append(
            Paper(
                title=w.get("title") or "",
                authors=authors,
                year=w.get("publication_year"),
                venue=venue,
                doi=doi,
                url=w.get("id") or "",
                abstract=_abstract_from_inverted(w.get("abstract_inverted_index")),
                citation_count=w.get("cited_by_count", 0) or 0,
                source="openalex",
            )
        )
    return out


# ── Semantic Scholar ─────────────────────────────────────────────────────────

def search_semantic_scholar(query: str, limit: int = 20, year_from: Optional[int] = None) -> list[Paper]:
    fields = "title,authors,year,venue,externalIds,citationCount,abstract,url"
    params = {"query": query, "limit": min(limit, 100), "fields": fields}
    if year_from:
        params["year"] = f"{year_from}-"
    headers = {"User-Agent": USER_AGENT}
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key

    with httpx.Client(timeout=HTTP_TIMEOUT, headers=headers) as client:
        r = client.get(SEMANTIC_SCHOLAR_URL, params=params)
        r.raise_for_status()
        data = r.json()

    out: list[Paper] = []
    for p in data.get("data", []):
        authors = tuple(a.get("name", "") for a in (p.get("authors") or []))
        ext = p.get("externalIds") or {}
        out.append(
            Paper(
                title=p.get("title") or "",
                authors=authors,
                year=p.get("year"),
                venue=p.get("venue") or "",
                doi=ext.get("DOI", "") or "",
                url=p.get("url", "") or "",
                abstract=p.get("abstract") or "",
                citation_count=p.get("citationCount", 0) or 0,
                source="semantic_scholar",
            )
        )
    return out


# ── Elicit (optional, requires API key) ──────────────────────────────────────

def search_elicit(query: str, limit: int = 20) -> list[Paper]:
    api_key = os.getenv("ELICIT_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ELICIT_API_KEY not set. Elicit's API requires a paid plan; "
            "set ELICIT_API_KEY in your .env or use --source openalex."
        )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
    }
    payload = {"query": query, "limit": min(limit, 50)}
    with httpx.Client(timeout=HTTP_TIMEOUT, headers=headers) as client:
        r = client.post(ELICIT_URL, json=payload)
        r.raise_for_status()
        data = r.json()

    out: list[Paper] = []
    for p in data.get("results", []):
        authors = tuple(a.get("name", "") if isinstance(a, dict) else str(a) for a in (p.get("authors") or []))
        out.append(
            Paper(
                title=p.get("title") or "",
                authors=authors,
                year=p.get("year"),
                venue=p.get("journal", "") or p.get("venue", ""),
                doi=p.get("doi", "") or "",
                url=p.get("url", "") or "",
                abstract=p.get("abstract") or p.get("summary") or "",
                citation_count=p.get("citation_count", 0) or 0,
                source="elicit",
            )
        )
    return out


# ── Output ───────────────────────────────────────────────────────────────────

def to_bibtex(paper: Paper) -> str:
    citekey = paper.suggested_citekey
    lines = [f"@article{{{citekey},"]
    if paper.authors:
        lines.append(f"  author = {{{' and '.join(paper.authors)}}},")
    if paper.title:
        lines.append(f"  title = {{{paper.title}}},")
    if paper.year:
        lines.append(f"  year = {{{paper.year}}},")
    if paper.venue:
        lines.append(f"  journal = {{{paper.venue}}},")
    if paper.doi:
        lines.append(f"  doi = {{{paper.doi}}},")
    if paper.url:
        lines.append(f"  url = {{{paper.url}}},")
    if paper.abstract:
        clean_abs = paper.abstract.replace("{", "(").replace("}", ")")
        lines.append(f"  abstract = {{{clean_abs}}},")
    lines.append("}")
    return "\n".join(lines)


def render_table(papers: list[Paper], query: str) -> None:
    t = Table(title=f"Discover: '{query}' ({len(papers)} hits)", show_lines=False)
    t.add_column("Year", style="cyan", width=4)
    t.add_column("Authors", style="green", width=25)
    t.add_column("Title", style="white")
    t.add_column("Cites", style="dim", width=6)
    t.add_column("DOI", style="dim", width=22)
    for p in papers:
        authors = ", ".join(a.split()[-1] for a in p.authors[:2] if a)
        if len(p.authors) > 2:
            authors += " et al."
        title = (p.title or "")[:80]
        t.add_row(str(p.year or ""), authors, title, str(p.citation_count), p.doi or "")
    console.print(t)


# ── CLI ──────────────────────────────────────────────────────────────────────

SOURCES = ("openalex", "semantic_scholar", "elicit")


@click.command()
@click.argument("query")
@click.option("--source", "-s", default="openalex", type=click.Choice(SOURCES),
              help="Which API to search.")
@click.option("--limit", "-n", default=15, type=int, help="Max results.")
@click.option("--year-from", default=None, type=int,
              help="Only return papers published in or after this year.")
@click.option("--export", "export_format", default=None,
              type=click.Choice(["bibtex", "json"]),
              help="Export results.")
@click.option("--sort", default="relevance",
              type=click.Choice(["relevance", "citations", "year"]),
              help="Sort order for the displayed table.")
def main(query, source, limit, year_from, export_format, sort):
    """Discover papers from external indices to import into Zotero."""
    try:
        if source == "openalex":
            papers = search_openalex(query, limit=limit, year_from=year_from)
        elif source == "semantic_scholar":
            papers = search_semantic_scholar(query, limit=limit, year_from=year_from)
        elif source == "elicit":
            papers = search_elicit(query, limit=limit)
        else:
            click.echo(f"Unknown source: {source}", err=True)
            sys.exit(1)
    except httpx.HTTPStatusError as e:
        console.print(f"[red]API error ({source}): {e.response.status_code} {e.response.text[:200]}[/red]")
        sys.exit(1)
    except (httpx.RequestError, RuntimeError) as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    if not papers:
        console.print(f"[yellow]No results for '{query}' on {source}.[/yellow]")
        return

    if sort == "citations":
        papers.sort(key=lambda p: p.citation_count or 0, reverse=True)
    elif sort == "year":
        papers.sort(key=lambda p: p.year or 0, reverse=True)

    if export_format == "bibtex":
        for p in papers:
            click.echo(to_bibtex(p) + "\n")
        return

    if export_format == "json":
        click.echo(
            json.dumps(
                [
                    {
                        "title": p.title,
                        "authors": list(p.authors),
                        "year": p.year,
                        "venue": p.venue,
                        "doi": p.doi,
                        "url": p.url,
                        "abstract": p.abstract,
                        "citation_count": p.citation_count,
                        "source": p.source,
                        "suggested_citekey": p.suggested_citekey,
                    }
                    for p in papers
                ],
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    render_table(papers, query)
    console.print(
        f"\n[dim]Source: {source}. "
        f"Use --export bibtex to dump entries for Zotero import.[/dim]"
    )


if __name__ == "__main__":
    main()
