#!/usr/bin/env python3
"""coherence.py — check multi-paragraph flow for a thesis chapter.

For each pair of adjacent paragraphs, asks: does paragraph N+1 follow from
paragraph N? Reports breaks in topic flow, redundant paragraphs, and
whether the chapter collectively delivers its stated thesis.

Does NOT rewrite. Outputs a critique with paragraph indices.

Usage:
    ./coherence.py drafts/chapter1.md --thesis "NUMT filtering is mandatory for clinical mtDNA pipelines"
    ./coherence.py drafts/ch1.md --thesis "..." --model sonnet
"""
from __future__ import annotations

import re
import sys

import click
from rich.console import Console
from rich.markdown import Markdown

from common import MODELS, ask_model, read_file

console = Console()


def split_paragraphs(text: str) -> list[str]:
    """Split a draft into paragraphs by blank lines, dropping pure-heading blocks."""
    blocks = re.split(r"\n\s*\n", text)
    out: list[str] = []
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        if all(line.strip().startswith(("#", "-", "*", ">", "|")) for line in b.splitlines()):
            continue
        out.append(b)
    return out


def build_paragraph_block(paragraphs: list[str], max_chars: int = 600) -> str:
    """Number paragraphs and truncate each to keep the prompt focused on transitions."""
    lines = []
    for i, p in enumerate(paragraphs, 1):
        excerpt = p[:max_chars].replace("\n", " ")
        if len(p) > max_chars:
            excerpt += " [...truncated]"
        lines.append(f"### Paragraph {i} ({len(p)} chars)\n{excerpt}")
    return "\n\n".join(lines)


PROMPT_TEMPLATE = """You are reviewing a thesis chapter draft for coherence and structure.
Do NOT rewrite. Identify issues only.

## Chapter thesis (what this chapter must deliver)
{thesis}

## Numbered paragraphs (truncated for transition focus)
{paragraphs}

## Your task — produce a structured report with these sections

### 1. Topic-flow breaks
List paragraph pairs (N → N+1) where the transition is abrupt, missing,
or the order seems wrong. Quote one short phrase from each side to anchor
the issue. For each break, say WHY it breaks (new topic without bridge,
out-of-order step, etc.).

### 2. Redundancy
Identify paragraphs that restate earlier paragraphs. Cite paragraph numbers
and the specific overlapping claim. Do NOT suggest merged prose.

### 3. Thesis support
For each paragraph, mark one of:
  - SUPPORTS (advances the thesis)
  - SETS_UP (necessary background)
  - OFF_TOPIC (does not contribute)
  - WEAKENS (raises an objection that is not handled)

Then summarize: which paragraphs are doing the heavy lifting, and which
should be cut or relocated.

### 4. Missing pieces
What the chapter would need to make the thesis fully defensible. Be
specific (e.g. "no paragraph addresses cost of filtering" or "no
quantitative comparison with X"). Do NOT propose replacement prose.

### 5. Recommended paragraph order
A reordered list of paragraph numbers (e.g. 1, 2, 4, 3, 5) IF the current
order is suboptimal. If it is fine, say "Current order is sound" and
explain in one line why.

Be specific. Be concise. Reference paragraphs by number. Never write
prose I could paraphrase into the draft.
"""


@click.command()
@click.argument("draft_file")
@click.option("--thesis", "-T", required=True,
              help="One sentence describing what the chapter must deliver.")
@click.option("--model", "-m", default="claude",
              type=click.Choice(list(MODELS.keys())),
              help="Which model to use.")
@click.option("--temperature", "-t", default=0.2, type=float,
              help="Model temperature (0.0–2.0).")
@click.option("--max-chars-per-paragraph", default=600, type=int,
              help="Truncate each paragraph in the prompt to this many chars.")
@click.option("--raw", is_flag=True, help="Print raw text instead of rendered markdown.")
def main(draft_file, thesis, model, temperature, max_chars_per_paragraph, raw):
    draft = read_file(draft_file)
    paragraphs = split_paragraphs(draft)
    if len(paragraphs) < 2:
        console.print(
            "[yellow]Need at least 2 paragraphs for a coherence pass.[/yellow]"
        )
        sys.exit(1)

    block = build_paragraph_block(paragraphs, max_chars=max_chars_per_paragraph)
    prompt = PROMPT_TEMPLATE.format(thesis=thesis, paragraphs=block)

    console.print(
        f"[dim]→ {model} | paragraphs: {len(paragraphs)} | thesis: {thesis}[/dim]\n"
    )
    result = ask_model(prompt, model=model, temperature=temperature, max_tokens=5000)

    if raw:
        click.echo(result["text"])
    else:
        console.print(Markdown(result["text"]))

    if result.get("input_tokens"):
        console.print(
            f"\n[dim]tokens: {result['input_tokens']} in, "
            f"{result['output_tokens']} out"
            + (f" | cost: ~${result['cost']:.4f}" if result.get("cost") else "")
            + "[/dim]"
        )


if __name__ == "__main__":
    main()
