#!/usr/bin/env python3
"""mermaid_figures.py — replace [FIGURE: description] placeholders with Mermaid diagrams.

Uses Claude to generate Mermaid syntax for each figure description, then
renders them to PNG via mmdc. Claude natively understands Mermaid syntax.

Usage:
    ./mermaid_figures.py paper.md              # adds mermaid blocks, renders to PNG
    ./mermaid_figures.py paper.md --no-render   # only add mermaid, skip PNG rendering
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import click

from agentic.bridge import call_agent

SYSTEM = """You are a diagram generation assistant. Given a figure description from an academic review article, generate a complete Mermaid diagram that visually represents the data described.

Choose the best Mermaid diagram type:
- xychart-beta: for bar charts, line charts, quantitative comparisons
- flowchart: for process flows, technology relationships, ecosystem maps
- quadrantChart: for 2x2 positioning (companies by funding vs maturity, etc.)
- timeline: for chronological milestones, regulatory history
- gantt: for project timelines, clinical trial phases
- pie: for market share, segmentation data
- mindmap: for hierarchical topic breakdowns

Rules:
1. Output ONLY the Mermaid code block — no explanations, no markdown outside the block
2. Use REAL data from the description — company names, numbers, dates, percentages
3. Keep diagrams clean and readable — 5-10 nodes max for flowcharts, 5-8 bars for charts
4. Add a title to every diagram
5. Use %% comments for any notes

Output format:
```mermaid
<diagram type>
<diagram content>
```"""

FIGURE_RE = re.compile(r"\[FIGURE:\s*(.*?)\]")


def extract_figures(text: str) -> list[tuple[int, int, str]]:
    """Find all [FIGURE: description] placeholders. Returns [(start, end, description), ...]."""
    return [(m.start(), m.end(), m.group(1).strip()) for m in FIGURE_RE.finditer(text)]


def generate_mermaid(description: str, figure_num: int, paper_context: str = "") -> str:
    """Use Claude to generate a Mermaid diagram for a figure description."""
    prompt = f"""Generate a Mermaid diagram for this figure from an academic review article.

Figure {figure_num}:
{description}

Paper context (for data reference):
{paper_context[:2000]}

Choose the best Mermaid diagram type for this data. Output ONLY the ```mermaid code block."""

    result = call_agent(prompt=prompt, model="claude", system=SYSTEM, temperature=0.2)

    text = result["text"].strip()

    # Extract just the mermaid block
    m = re.search(r"```mermaid\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()

    # If no code block, use the raw text (might be valid mermaid)
    return text


def add_mermaid_to_paper(paper_path: Path, paper_context: str = "") -> str:
    """Read paper, replace [FIGURE: desc] with Mermaid diagrams, return new text."""
    text = paper_path.read_text(encoding="utf-8")
    figures = extract_figures(text)

    if not figures:
        print("No [FIGURE: ...] placeholders found.")
        return text

    print(f"Found {len(figures)} figure placeholders.\n")

    # Replace from end to start so positions stay valid
    for i, (start, end, desc) in enumerate(reversed(figures), 1):
        fig_num = len(figures) - i + 1
        print(f"  Generating Figure {fig_num}: {desc[:80]}...", file=sys.stderr)

        mermaid_code = generate_mermaid(desc, fig_num, paper_context)

        # Build replacement: newline + mermaid block + newline
        mermaid_block = f"\n\n**Figure {fig_num}:** {desc}\n\n```mermaid\n{mermaid_code}\n```\n\n"
        text = text[:start] + mermaid_block + text[end:]

    return text


@click.command()
@click.argument("paper", type=click.Path(exists=True))
@click.option("--no-render", is_flag=True, help="Skip PNG rendering.")
@click.option("--scale", "-s", default=2, type=int, help="PNG scale factor.")
def main(paper, no_render, scale):
    """Replace [FIGURE: ...] placeholders with Mermaid diagrams."""
    paper_path = Path(paper).resolve()
    text = paper_path.read_text(encoding="utf-8")

    # Use first 3000 chars as context for the LLM
    context = text[:3000]

    print(f"Paper: {paper_path}")
    print(f"Size: {len(text)} chars\n")

    new_text = add_mermaid_to_paper(paper_path, context)

    # Backup original
    backup = paper_path.with_suffix(".md.bak")
    paper_path.rename(backup)
    paper_path.write_text(new_text, encoding="utf-8")
    print(f"\nUpdated {paper_path} (backup: {backup})")

    # Count mermaid blocks
    mermaid_count = len(re.findall(r"```mermaid", new_text))
    print(f"Mermaid diagrams: {mermaid_count}")

    # Render to PNG
    if not no_render and mermaid_count > 0:
        print("\nRendering PNGs...")
        from render_mermaid import render_all
        fig_dir = paper_path.parent / f"{paper_path.stem}_figures"
        rendered = render_all(paper_path, fig_dir, scale)
        print(f"Rendered {len(rendered)} PNGs to {fig_dir}/")


if __name__ == "__main__":
    main()
