#!/usr/bin/env python3
"""paraphrase_check.py — flag draft paragraphs that are too close to source chunks.

Embeds each paragraph in your draft and queries the existing Chroma index
for the nearest source chunks. Paragraphs with cosine similarity above the
threshold are flagged so you can rewrite them in your own words before
submission.

This complements verify.py: verify catches missing citations, this catches
near-verbatim paraphrasing of your own indexed papers.

Usage:
    ./paraphrase_check.py drafts/ch1_full.md
    ./paraphrase_check.py drafts/ch1.md --threshold 0.82 --top 3
    ./paraphrase_check.py drafts/ch1.md --min-chars 250 --json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from common import read_file
from researcher import (
    DEFAULT_EMBED_MODEL,
    _embed_single,
    _get_collection,
    _get_index_meta,
    CHROMA_DIR,
)

console = Console()

DEFAULT_THRESHOLD = 0.85
DEFAULT_TOP = 2
DEFAULT_MIN_CHARS = 150


def split_paragraphs(text: str) -> list[str]:
    """Split a draft into paragraphs by blank lines. Strips markdown headings."""
    blocks = re.split(r"\n\s*\n", text)
    out: list[str] = []
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        # Skip headings, list-only blocks, and citation-only lines.
        if all(line.strip().startswith(("#", "-", "*", ">", "|")) for line in b.splitlines()):
            continue
        out.append(b)
    return out


def find_near_matches(
    paragraph: str,
    collection,
    top: int = DEFAULT_TOP,
    threshold: float = DEFAULT_THRESHOLD,
    embedding_model: str = DEFAULT_EMBED_MODEL,
) -> list[dict]:
    """Return top-N chunks from the index for this paragraph, filtered by threshold."""
    emb = _embed_single(paragraph, model=embedding_model)
    results = collection.query(
        query_embeddings=[emb],
        n_results=top,
        include=["documents", "metadatas", "distances"],
    )
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    matches: list[dict] = []
    for doc, meta, dist in zip(docs, metas, dists):
        if doc is None or meta is None or dist is None:
            continue
        sim = 1.0 - dist
        if sim >= threshold:
            matches.append(
                {
                    "similarity": round(sim, 4),
                    "text": doc,
                    "citekey": meta.get("citekey", ""),
                    "title": meta.get("title", ""),
                    "authors_short": meta.get("authors_short", ""),
                    "year": meta.get("year", ""),
                }
            )
    return matches


@click.command()
@click.argument("draft_file")
@click.option("--threshold", "-t", default=DEFAULT_THRESHOLD, type=float,
              help="Cosine similarity threshold (0–1). Higher = stricter.")
@click.option("--top", "-k", default=DEFAULT_TOP, type=int,
              help="Top-N nearest chunks per paragraph (default 2).")
@click.option("--min-chars", default=DEFAULT_MIN_CHARS, type=int,
              help="Skip paragraphs shorter than this many characters.")
@click.option("--embedding-model", default=DEFAULT_EMBED_MODEL,
              help="Embedding model (must match the index).")
@click.option("--json", "as_json", is_flag=True, help="Output JSON instead of a table.")
@click.option("--show-source", is_flag=True,
              help="Print the matched source excerpt next to each flagged paragraph.")
def main(draft_file, threshold, top, min_chars, embedding_model, as_json, show_source):
    if not CHROMA_DIR.exists():
        console.print("[red]No index found. Run './researcher.py index' first.[/red]")
        sys.exit(1)

    text = read_file(draft_file)
    paragraphs = split_paragraphs(text)
    if not paragraphs:
        console.print("[yellow]No paragraphs found in draft.[/yellow]")
        return

    collection = _get_collection()
    meta = _get_index_meta(collection)
    if meta and meta.get("embedding_model") != embedding_model:
        console.print(
            f"[yellow]Warning: index was built with {meta['embedding_model']}, "
            f"querying with {embedding_model}.[/yellow]"
        )

    flagged: list[dict] = []
    skipped = 0
    for i, para in enumerate(paragraphs, 1):
        if len(para) < min_chars:
            skipped += 1
            continue
        matches = find_near_matches(
            para,
            collection=collection,
            top=top,
            threshold=threshold,
            embedding_model=embedding_model,
        )
        if matches:
            flagged.append({"paragraph_index": i, "text": para, "matches": matches})

    if as_json:
        click.echo(json.dumps(flagged, indent=2, ensure_ascii=False))
        return

    console.print(
        f"\n[bold]Paraphrase check: {draft_file}[/bold]\n"
        f"[dim]Paragraphs scanned: {len(paragraphs) - skipped} "
        f"(skipped {skipped} under {min_chars} chars) | threshold: {threshold}[/dim]\n"
    )

    if not flagged:
        console.print("[green]✓ No paragraphs exceeded the similarity threshold.[/green]")
        return

    table = Table(title="Flagged paragraphs", show_lines=True)
    table.add_column("#", style="cyan", width=4)
    table.add_column("Top match", style="white", width=40)
    table.add_column("Similarity", style="red", width=10)
    table.add_column("Paragraph excerpt", style="dim", width=50)

    for entry in flagged:
        top_match = entry["matches"][0]
        cite = f"@{top_match['citekey']}" if top_match["citekey"] else "(no citekey)"
        match_label = f"{cite} — {top_match['authors_short']} ({top_match['year']})"
        para_excerpt = entry["text"][:200].replace("\n", " ")
        if len(entry["text"]) > 200:
            para_excerpt += "..."
        table.add_row(
            str(entry["paragraph_index"]),
            match_label,
            f"{top_match['similarity']:.3f}",
            para_excerpt,
        )
    console.print(table)

    if show_source:
        console.print("\n[bold]Details[/bold]")
        for entry in flagged:
            console.print(
                Panel(
                    Markdown(entry["text"]),
                    title=f"Paragraph #{entry['paragraph_index']} (yours)",
                    border_style="yellow",
                )
            )
            for m in entry["matches"]:
                cite = f"@{m['citekey']}" if m["citekey"] else "(no citekey)"
                console.print(
                    Panel(
                        Markdown(m["text"][:800]),
                        title=f"Source: {cite} — sim {m['similarity']:.3f}",
                        border_style="red",
                    )
                )

    sys.exit(1)


if __name__ == "__main__":
    main()
