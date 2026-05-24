"""Originality check: combines internal RAG similarity with external academic search.

NOT a true plagiarism detector. Produces leads for human review.

Usage:
    ra-originality drafts/ch1.md
    ra-originality drafts/ch1.md --sources internal,openalex --internal-threshold 0.80
"""
from __future__ import annotations

import json as _json
import math
import sys
from typing import Literal

import click
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from research_assistant.common import read_file
from research_assistant.researcher import (
    CHROMA_DIR,
    DEFAULT_EMBED_MODEL,
    _embed_single,
    _get_collection,
)
from research_assistant.verification import external_match as _em
from research_assistant.verification.paraphrase_check import split_paragraphs

DEFAULT_INTERNAL_THRESHOLD = 0.85
DEFAULT_EXTERNAL_THRESHOLD = 0.80
DEFAULT_MIN_CHARS = 150
DEFAULT_SOURCES: tuple[str, ...] = ("internal", "openalex", "crossref")
EXTERNAL_FETCH_LIMIT = 5

_console = Console()


class ExternalMatch(BaseModel):
    """A single match for a paragraph from one source."""

    source: Literal["internal", "openalex", "crossref"]
    similarity: float
    title: str
    authors: str | None = None
    year: int | None = None
    doi: str | None = None
    citekey: str | None = None         # only for internal matches
    excerpt: str = ""                  # snippet that matched
    url: str | None = None


class ParagraphReport(BaseModel):
    index: int
    text: str
    matches: list[ExternalMatch]

    @property
    def severity(self) -> Literal["green", "yellow", "red"]:
        if not self.matches:
            return "green"
        max_sim = max(m.similarity for m in self.matches)
        return "red" if max_sim >= 0.92 else "yellow"


class OriginalityReport(BaseModel):
    paragraphs: list[ParagraphReport]

    @property
    def summary(self) -> str:
        red = sum(1 for p in self.paragraphs if p.severity == "red")
        yellow = sum(1 for p in self.paragraphs if p.severity == "yellow")
        return f"{red} red flag(s), {yellow} yellow flag(s)"


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _internal_matches(paragraph: str, threshold: float) -> list[ExternalMatch]:
    """Cosine-similarity matches against the local Chroma index (your indexed library)."""
    if not CHROMA_DIR.exists():
        return []
    collection = _get_collection()
    emb = _embed_single(paragraph, model=DEFAULT_EMBED_MODEL)
    results = collection.query(
        query_embeddings=[emb],
        n_results=5,
        include=["documents", "metadatas", "distances"],
    )
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    out: list[ExternalMatch] = []
    for doc, meta, dist in zip(docs, metas, dists, strict=False):
        if doc is None or meta is None or dist is None:
            continue
        sim = 1.0 - dist
        if sim < threshold:
            continue
        out.append(
            ExternalMatch(
                source="internal",
                similarity=round(sim, 4),
                title=meta.get("title", "") or "",
                authors=meta.get("authors_short") or None,
                year=int(meta["year"]) if (meta.get("year") or "").isdigit() else None,
                doi=meta.get("doi") or None,
                citekey=meta.get("citekey") or None,
                excerpt=doc[:300],
            )
        )
    return out


def _external_matches_from(source: str, paragraph: str, threshold: float) -> list[ExternalMatch]:
    """Shared OpenAlex/Crossref helper. Cosine sim is computed from abstracts."""
    candidates = _em.cached_search(source, paragraph, limit=EXTERNAL_FETCH_LIMIT)
    if not candidates:
        return []

    para_emb = _embed_single(paragraph, model=DEFAULT_EMBED_MODEL)
    out: list[ExternalMatch] = []
    for cand in candidates:
        abstract = (cand.get("abstract") or "").strip()
        if not abstract:
            continue
        cand_emb = _embed_single(abstract, model=DEFAULT_EMBED_MODEL)
        sim = _cosine(para_emb, cand_emb)
        if sim < threshold:
            continue
        out.append(
            ExternalMatch(
                source=source,                         # type: ignore[arg-type]
                similarity=round(sim, 4),
                title=cand.get("title", "") or "",
                authors=cand.get("authors"),
                year=cand.get("year"),
                doi=cand.get("doi"),
                excerpt=abstract[:300],
                url=cand.get("url"),
            )
        )
    return out


def _external_matches_openalex(paragraph: str, threshold: float) -> list[ExternalMatch]:
    return _external_matches_from("openalex", paragraph, threshold)


def _external_matches_crossref(paragraph: str, threshold: float) -> list[ExternalMatch]:
    return _external_matches_from("crossref", paragraph, threshold)


def check_originality(
    draft_path: str,
    *,
    sources: tuple[str, ...] = DEFAULT_SOURCES,
    internal_threshold: float = DEFAULT_INTERNAL_THRESHOLD,
    external_threshold: float = DEFAULT_EXTERNAL_THRESHOLD,
    min_chars: int = DEFAULT_MIN_CHARS,
) -> OriginalityReport:
    """Run all configured sources against every substantive paragraph in the draft."""
    text = read_file(draft_path)
    paragraphs = [p for p in split_paragraphs(text) if len(p) >= min_chars]

    report_paragraphs: list[ParagraphReport] = []
    for i, para in enumerate(paragraphs):
        matches: list[ExternalMatch] = []
        if "internal" in sources:
            matches += _internal_matches(para, internal_threshold)
        if "openalex" in sources:
            matches += _external_matches_openalex(para, external_threshold)
        if "crossref" in sources:
            matches += _external_matches_crossref(para, external_threshold)
        if matches:
            report_paragraphs.append(ParagraphReport(index=i, text=para, matches=matches))

    return OriginalityReport(paragraphs=report_paragraphs)


@click.command()
@click.argument("draft_file")
@click.option("--sources", default=",".join(DEFAULT_SOURCES),
              help="Comma-separated subset of: internal,openalex,crossref.")
@click.option("--internal-threshold", default=DEFAULT_INTERNAL_THRESHOLD, type=float,
              help="Min cosine similarity vs. your indexed library to flag (0-1).")
@click.option("--external-threshold", default=DEFAULT_EXTERNAL_THRESHOLD, type=float,
              help="Min cosine similarity vs. OpenAlex/Crossref abstracts (0-1).")
@click.option("--min-chars", default=DEFAULT_MIN_CHARS, type=int,
              help="Skip paragraphs shorter than this many characters.")
@click.option("--json", "as_json", is_flag=True,
              help="Output the OriginalityReport as JSON.")
def main(draft_file, sources, internal_threshold, external_threshold, min_chars, as_json):
    """Flag paragraphs that look too similar to indexed papers or to published abstracts."""
    src_tuple = tuple(s.strip() for s in sources.split(",") if s.strip())
    valid = {"internal", "openalex", "crossref"}
    invalid = set(src_tuple) - valid
    if invalid:
        click.echo(f"Unknown source(s): {sorted(invalid)}. Valid: {sorted(valid)}.", err=True)
        sys.exit(2)

    report = check_originality(
        draft_file,
        sources=src_tuple,
        internal_threshold=internal_threshold,
        external_threshold=external_threshold,
        min_chars=min_chars,
    )

    if as_json:
        click.echo(_json.dumps(report.model_dump(), indent=2, ensure_ascii=False))
        if any(p.severity == "red" for p in report.paragraphs):
            sys.exit(1)
        return

    _console.print(f"\n[bold]Originality check: {draft_file}[/bold]")
    _console.print(f"[dim]{report.summary}[/dim]\n")

    if not report.paragraphs:
        _console.print("[green]No paragraphs exceeded similarity thresholds.[/green]")
        return

    table = Table(title="Flagged paragraphs", show_lines=True)
    table.add_column("#", style="cyan", width=4)
    table.add_column("Severity", style="bold", width=8)
    table.add_column("Top match", style="white", width=44)
    table.add_column("Sim", style="red", width=6)
    table.add_column("Excerpt", style="dim", width=44)

    severity_style = {"red": "red", "yellow": "yellow", "green": "green"}
    for p in report.paragraphs:
        top = max(p.matches, key=lambda m: m.similarity)
        cite = f"@{top.citekey}" if top.citekey else (top.doi or top.url or "(no id)")
        label = f"[{top.source}] {cite} -- {top.title[:30]}"
        excerpt = p.text[:120].replace("\n", " ")
        if len(p.text) > 120:
            excerpt += "..."
        sev = p.severity
        table.add_row(
            str(p.index),
            f"[{severity_style[sev]}]{sev.upper()}[/{severity_style[sev]}]",
            label,
            f"{top.similarity:.2f}",
            excerpt,
        )
    _console.print(table)

    if any(p.severity == "red" for p in report.paragraphs):
        sys.exit(1)


if __name__ == "__main__":
    main()
