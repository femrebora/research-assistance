#!/usr/bin/env python3
"""outline.py — turn an evidence file + chapter/section job into a hierarchical outline.

This sits between evidence.py / researcher.py (gather citations) and your actual
writing. The output is a numbered outline with one-line stubs and [@citekey]
placeholders — never full prose you could paste in.

Usage:
    ./outline.py evidence/ch1/numt_clinical.md \\
        --job "Establish NUMT contamination as a clinically significant problem"

    ./outline.py evidence/ch1/numt_clinical.md \\
        --job "..." --sections 4 --depth 2 --model sonnet

    ./outline.py evidence/ch1/numt_clinical.md \\
        --job "..." --save outlines/ch1_numt.md
"""
from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.markdown import Markdown

from common import MODELS, ask_model, read_file, save_file

console = Console()

PROMPT_TEMPLATE = """You are helping me plan a thesis chapter / section. I will write
all prose myself. Your job is to produce a tight outline I can fill in.

## Section job (what this section must accomplish)
{job}

## Evidence retrieved from my library (with citations)
{evidence}

## Your task

Produce a hierarchical outline with the following constraints:

1. Top level: exactly {sections} main sections. Each section has a one-sentence
   "purpose" line (what the section achieves) and a numbered list of paragraph
   stubs under it.
2. Each paragraph stub is **one sentence describing the topic only** plus the
   [@citekey] citations that support it (drawn from the evidence above).
3. Nest sub-points up to {depth} levels deep when an idea genuinely splits.
4. If a sub-point lacks evidence in the provided list, mark it [needs evidence].
5. Do NOT write topic sentences as polished prose. Use note-taking style.
   "Define NUMT and clinical impact [@smith2024; @jones2023]" is right;
   "NUMTs are nuclear copies of mitochondrial DNA that..." is wrong.
6. End with a "## Coverage check" block listing any [@citekey] from the evidence
   that you did NOT place anywhere in the outline, with a one-line reason
   (off-topic, redundant, weaker than another source, etc.).

Format the outline as markdown with numbered headings and nested bullets.
"""


@click.command()
@click.argument("evidence_file")
@click.option("--job", "-j", required=True,
              help="One sentence describing what this section must accomplish.")
@click.option("--sections", "-s", default=3, type=int,
              help="Number of top-level sections (default 3).")
@click.option("--depth", "-d", default=2, type=int,
              help="Max nesting depth for sub-points (default 2).")
@click.option("--model", "-m", default="claude",
              type=click.Choice(list(MODELS.keys())),
              help="Which model to use.")
@click.option("--temperature", "-t", default=0.3, type=float,
              help="Model temperature (0.0–2.0).")
@click.option("--save", "-o", default=None,
              help="Save outline to this path (relative to THESIS_ROOT).")
@click.option("--raw", is_flag=True,
              help="Print raw text instead of rendered markdown.")
def main(evidence_file, job, sections, depth, model, temperature, save, raw):
    if sections < 1 or sections > 12:
        click.echo("Error: --sections must be 1–12.", err=True)
        sys.exit(1)
    if depth < 1 or depth > 4:
        click.echo("Error: --depth must be 1–4.", err=True)
        sys.exit(1)

    evidence = read_file(evidence_file)
    prompt = PROMPT_TEMPLATE.format(
        job=job,
        evidence=evidence,
        sections=sections,
        depth=depth,
    )

    console.print(
        f"[dim]→ {model} | sections={sections} depth={depth} | "
        f"job: {job}[/dim]\n"
    )
    result = ask_model(prompt, model=model, temperature=temperature, max_tokens=6000)
    output = result["text"]

    if save:
        header = f"""# Outline

**Job:** {job}
**Evidence file:** {evidence_file}
**Model:** {model} ({MODELS[model]})

---

"""
        path = save_file(save, header + output)
        console.print(f"[green]Outline saved: {path}[/green]\n")

    if raw:
        click.echo(output)
    else:
        console.print(Markdown(output))

    if result.get("input_tokens"):
        console.print(
            f"\n[dim]tokens: {result['input_tokens']} in, "
            f"{result['output_tokens']} out"
            + (f" | cost: ~${result['cost']:.4f}" if result.get("cost") else "")
            + "[/dim]"
        )


if __name__ == "__main__":
    main()
