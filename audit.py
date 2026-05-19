#!/usr/bin/env python3
"""audit.py — citation audit for a thesis draft.

Reports:
  - Citations per source (sorted desc), flagging over-cited papers (>N uses).
  - Unused .bib entries (defined but never cited).
  - Duplicate citekeys in the .bib (BibTeX would silently overwrite one).
  - Citation density: citations per 1000 words, per paragraph.
  - Single-source paragraphs (paragraph cites exactly one source).

Use this BEFORE you submit a chapter. Combine with verify.py (missing citations).

Usage:
    ./audit.py drafts/ch1_full.md --bib bib/thesis.bib
    ./audit.py drafts/ch1.md --over-cite 5 --json
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from common import read_file
from verify import CITE_RE, _CITEKEY_CHAR, extract_bib_keys, extract_draft_keys

console = Console()

DEFAULT_OVER_CITE = 6
DEFAULT_DENSITY_LOW = 0.5   # citations per 100 words
DEFAULT_DENSITY_HIGH = 8.0  # citations per 100 words

_KEY_INSIDE_RE = re.compile(rf"@({_CITEKEY_CHAR})")


def split_paragraphs(text: str) -> list[str]:
    blocks = re.split(r"\n\s*\n", text)
    return [b.strip() for b in blocks if b.strip()]


def paragraph_keys(paragraph: str) -> list[str]:
    """Citekeys cited in a single paragraph (in order, with repeats)."""
    keys: list[str] = []
    for match in CITE_RE.finditer(paragraph):
        keys.extend(_KEY_INSIDE_RE.findall(match.group(0)))
    return keys


def word_count(text: str) -> int:
    cleaned = re.sub(r"\[[^\]]*\]", "", text)  # drop [@key] blocks for fair count
    return len(re.findall(r"\b[\w'-]+\b", cleaned))


def find_duplicate_bib_keys(bib_text: str) -> list[tuple[str, int]]:
    """Return [(citekey, count), ...] for keys that appear more than once."""
    from verify import BIBKEY_RE
    counts = Counter(BIBKEY_RE.findall(bib_text))
    return [(k, c) for k, c in counts.most_common() if c > 1]


def build_audit(draft: str, bib_text: str, over_cite: int) -> dict:
    """Return a structured audit report."""
    paragraphs = split_paragraphs(draft)
    draft_keys = extract_draft_keys(draft)
    bib_keys = extract_bib_keys(bib_text)
    duplicates = find_duplicate_bib_keys(bib_text)

    per_source = Counter(draft_keys)
    over_cited = [(k, c) for k, c in per_source.most_common() if c > over_cite]
    unused = sorted(bib_keys - set(draft_keys))
    missing = sorted(set(draft_keys) - bib_keys)

    total_words = word_count(draft)
    total_cites = len(draft_keys)
    density_per_100w = (total_cites / total_words * 100.0) if total_words else 0.0

    paragraph_stats = []
    single_source_paragraphs = []
    for i, p in enumerate(paragraphs, 1):
        keys = paragraph_keys(p)
        unique = set(keys)
        words = word_count(p)
        paragraph_stats.append(
            {
                "index": i,
                "words": words,
                "citations": len(keys),
                "unique_sources": len(unique),
                "density_per_100w": (len(keys) / words * 100.0) if words else 0.0,
            }
        )
        if len(unique) == 1 and len(keys) >= 3 and words >= 80:
            single_source_paragraphs.append(
                {"index": i, "citekey": next(iter(unique)), "uses": len(keys), "words": words}
            )

    return {
        "total_words": total_words,
        "total_citations": total_cites,
        "unique_cited_sources": len(set(draft_keys)),
        "bib_entries": len(bib_keys),
        "density_per_100_words": round(density_per_100w, 2),
        "per_source": dict(per_source.most_common()),
        "over_cited": over_cited,
        "unused_bib_entries": unused,
        "missing_citations": missing,
        "duplicate_bib_keys": duplicates,
        "paragraphs": paragraph_stats,
        "single_source_paragraphs": single_source_paragraphs,
    }


def _render(report: dict) -> None:
    """Pretty-print an audit report via Rich."""
    summary = Table(title="Audit summary", show_header=False)
    summary.add_column(style="cyan")
    summary.add_column(style="green")
    summary.add_row("Words (excl. citation blocks)", str(report["total_words"]))
    summary.add_row("Total citations", str(report["total_citations"]))
    summary.add_row("Unique sources cited", str(report["unique_cited_sources"]))
    summary.add_row("Bibliography entries", str(report["bib_entries"]))
    summary.add_row("Citation density / 100 words", str(report["density_per_100_words"]))
    console.print(summary)

    # Per-source table
    if report["per_source"]:
        t = Table(title="Citations per source (top 20)")
        t.add_column("Citekey", style="cyan")
        t.add_column("Uses", style="green")
        for k, c in list(report["per_source"].items())[:20]:
            t.add_row(k, str(c))
        console.print(t)

    if report["over_cited"]:
        t = Table(title="Over-cited sources (possible single-source dependence)", border_style="yellow")
        t.add_column("Citekey", style="yellow")
        t.add_column("Uses", style="red")
        for k, c in report["over_cited"]:
            t.add_row(k, str(c))
        console.print(t)
    else:
        console.print("[green]✓ No over-cited sources.[/green]")

    if report["unused_bib_entries"]:
        console.print(
            Panel(
                ", ".join(report["unused_bib_entries"][:60])
                + (" ..." if len(report["unused_bib_entries"]) > 60 else ""),
                title=f"Unused .bib entries ({len(report['unused_bib_entries'])})",
                border_style="dim",
            )
        )

    if report["missing_citations"]:
        console.print(
            Panel(
                ", ".join(report["missing_citations"]),
                title=f"Missing in .bib ({len(report['missing_citations'])})",
                border_style="red",
            )
        )
    else:
        console.print("[green]✓ All citations resolve to .bib.[/green]")

    if report["duplicate_bib_keys"]:
        t = Table(title="Duplicate citekeys in .bib", border_style="red")
        t.add_column("Citekey", style="red")
        t.add_column("Appearances", style="yellow")
        for k, c in report["duplicate_bib_keys"]:
            t.add_row(k, str(c))
        console.print(t)

    if report["single_source_paragraphs"]:
        t = Table(title="Paragraphs leaning on a single source", border_style="yellow")
        t.add_column("Paragraph", style="cyan")
        t.add_column("Citekey", style="yellow")
        t.add_column("Uses", style="dim")
        t.add_column("Words", style="dim")
        for p in report["single_source_paragraphs"]:
            t.add_row(str(p["index"]), p["citekey"], str(p["uses"]), str(p["words"]))
        console.print(t)


@click.command()
@click.argument("draft_file")
@click.option("--bib", default="bib/thesis.bib",
              help="Path to .bib file (relative to THESIS_ROOT).")
@click.option("--over-cite", default=DEFAULT_OVER_CITE, type=int,
              help="Flag sources cited more than this many times.")
@click.option("--json", "as_json", is_flag=True, help="Output JSON instead of tables.")
def main(draft_file, bib, over_cite, as_json):
    draft = read_file(draft_file)
    bib_text = read_file(bib)
    report = build_audit(draft, bib_text, over_cite=over_cite)

    if as_json:
        click.echo(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        console.print(f"\n[bold]Citation audit: {draft_file}[/bold]\n")
        _render(report)

    # Exit non-zero if there are missing citations or duplicate bib keys.
    if report["missing_citations"] or report["duplicate_bib_keys"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
