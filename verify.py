#!/usr/bin/env python3
"""verify.py — check that all [@citekey] placeholders in a draft exist in your .bib.

Catches hallucinated citations before submission.

Usage:
    ./verify.py drafts/ch1_full.md --bib bib/thesis.bib
    ./verify.py drafts/ch1_full.md  # uses bib/thesis.bib by default
"""
from __future__ import annotations

import re
import sys
from collections import Counter

import click
from rich.console import Console
from rich.table import Table

from common import read_file

console = Console()

# Matches pandoc citation syntax: [@citekey], [@citekey2024], [-@citekey],
# [@citekey; @citekey2], and bare @citekey references.
# Bare @key is only matched when not preceded by a word char, '.', or '/',
# so emails (me@example.com) and paths don't get flagged as citations.
_CITEKEY_CHAR = r"[a-zA-Z][a-zA-Z0-9_:-]*"

# A single citation unit inside brackets, with an optional Pandoc locator:
#   @citekey                  simple citation
#   @citekey, p. 42           citation with locator
#   -@citekey, ch. 3          suppressed-author with locator
# The locator text may contain commas (pp. 33-35, 38-39) but not @, ;, [, or ].
_CITE_UNIT = rf"-?@{_CITEKEY_CHAR}(?:,\s*[^@;\[\]]+)?"

CITE_RE = re.compile(
    rf"(?<![\w./])@{_CITEKEY_CHAR}"
    rf"|\[{_CITE_UNIT}(?:\s*;\s*{_CITE_UNIT})*\]"
)

# BibTeX entry: @article{citekey, ...
BIBKEY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,", re.MULTILINE)


def extract_draft_keys(text: str) -> list[str]:
    """Extract individual citekeys from all pandoc citation matches."""
    keys = []
    for match in CITE_RE.finditer(text):
        inner = match.group(0)
        keys.extend(re.findall(rf"@{_CITEKEY_CHAR}", inner))
    return [k.lstrip("@") for k in keys]


def extract_bib_keys(bib_text: str) -> set[str]:
    return set(BIBKEY_RE.findall(bib_text))


@click.command()
@click.argument("draft_file")
@click.option("--bib", default="bib/thesis.bib",
              help="Path to .bib file (relative to THESIS_ROOT).")
def main(draft_file, bib):
    draft = read_file(draft_file)
    bib_text = read_file(bib)

    draft_keys = extract_draft_keys(draft)
    bib_keys = extract_bib_keys(bib_text)

    if not draft_keys:
        console.print("[yellow]No citations found in draft.[/yellow]")
        return

    missing = []
    found = []
    for k in draft_keys:
        if k in bib_keys:
            found.append(k)
        else:
            missing.append(k)

    console.print(f"\n[bold]Citation check: {draft_file}[/bold]")
    console.print(f"Total citations in draft: {len(draft_keys)} ({len(set(draft_keys))} unique)")
    console.print(f"Bibliography entries: {len(bib_keys)}")
    console.print(f"[green]Resolved: {len(found)}[/green]")
    console.print(f"[red]Missing: {len(set(missing))}[/red]\n")

    if missing:
        table = Table(title="Missing citations (check for typos or add to Zotero)")
        table.add_column("Citekey", style="red")
        table.add_column("Count", style="dim")
        for key, count in Counter(missing).most_common():
            table.add_row(key, str(count))
        console.print(table)
        sys.exit(1)
    else:
        console.print("[green]✓ All citations resolved.[/green]")


if __name__ == "__main__":
    main()
