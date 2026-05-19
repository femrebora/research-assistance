#!/usr/bin/env python3
"""critique.py — get critique of a paragraph YOU have written.

This script does NOT rewrite your prose. It identifies issues you should fix.
You decide what to do about them.

Usage:
    ./critique.py drafts/ch1_para_3.md \\
        --job "Establish NUMT contamination as a clinically significant problem"

    # Diff mode: output as unified-diff style annotations alongside your draft.
    ./critique.py drafts/ch1_para_3.md --job "..." --diff

    # Or paste from stdin (e.g. copy from Google Docs):
    pbpaste | ./critique.py --stdin \\
        --job "..." --model gemini
"""
from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.markdown import Markdown

from common import MODELS, ask_model, read_file

console = Console()

PROMPT_TEMPLATE = """I have written a paragraph for my thesis. Critique it. Do NOT rewrite it.

## Job this paragraph must do
{job}

## My paragraph (written by me)
{draft}

## Your task

Identify issues with this paragraph. Be specific and direct. Cover:

1. **Clarity**: What is unclear or could be misread?
2. **Argument**: What claim is unsupported, hand-wavy, or overstated?
3. **Citations**: What claim seems to need a citation but lacks one? What citation would strengthen a specific sentence?
4. **Committee challenge**: What would a skeptical thesis committee member object to or ask about?
5. **Job fit**: Does the paragraph actually do the job stated above? If not, what's missing or off-topic?
6. **Structure**: Is the paragraph well-ordered, or do ideas come in a confusing sequence?

Format as a numbered list under each heading. Be concise. Do NOT rewrite the paragraph.
Do NOT provide replacement prose. If a sentence is weak, say WHY it is weak, not how to fix it.
"""

DIFF_PROMPT_TEMPLATE = """I have written a paragraph for my thesis. Annotate it with critique.
You may NOT propose replacement wording. You may only point at sentences.

## Job this paragraph must do
{job}

## My paragraph (one sentence per line, numbered)
{numbered}

## Your task

For each sentence number, output AT MOST one annotation line in the form:

  S<n> [TAG]: short critique question (no replacement prose).

Tags (use the most specific one):
  CLARITY     — unclear or could be misread
  CLAIM       — unsupported or hand-wavy claim
  CITE        — needs a citation
  OVERREACH   — overstated relative to evidence
  ORDER       — comes out of logical sequence
  OFF_JOB     — does not contribute to the stated job
  COMMITTEE   — a committee member would object here

If a sentence is fine, omit it from your output entirely. Do NOT write
replacement sentences. Do NOT quote more than 6 consecutive words from
my paragraph. End your output with one line:

  SUMMARY: <one sentence on the paragraph's overall problem, if any>
"""


def _number_sentences(text: str) -> str:
    """Split into sentences and number them, one per line."""
    import re
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    lines = []
    for i, s in enumerate(sentences, 1):
        if s.strip():
            lines.append(f"S{i}: {s.strip()}")
    return "\n".join(lines)


@click.command()
@click.argument("draft_file", required=False)
@click.option("--job", "-j", required=True,
              help="One sentence describing what this paragraph must do.")
@click.option("--stdin", "use_stdin", is_flag=True,
              help="Read draft from stdin instead of file.")
@click.option("--diff", "diff_mode", is_flag=True,
              help="Output sentence-anchored critique (S1, S2, ...) instead of prose review.")
@click.option("--model", default="claude",
              type=click.Choice(list(MODELS.keys())),
              help="Which model to use.")
@click.option("--temperature", "-t", default=0.2, type=float,
              help="Model temperature (0.0–2.0).")
@click.option("--raw", is_flag=True, help="Print raw text instead of rendered markdown.")
def main(draft_file, job, use_stdin, diff_mode, model, temperature, raw):
    if use_stdin:
        draft = sys.stdin.read()
    elif draft_file:
        draft = read_file(draft_file)
    else:
        click.echo("Error: provide a draft file or use --stdin", err=True)
        sys.exit(1)

    if len(draft.strip()) < 50:
        console.print("[yellow]Draft seems very short. Are you sure?[/yellow]")

    if diff_mode:
        prompt = DIFF_PROMPT_TEMPLATE.format(job=job, numbered=_number_sentences(draft))
    else:
        prompt = PROMPT_TEMPLATE.format(job=job, draft=draft)

    label = "diff" if diff_mode else "prose"
    console.print(f"[dim]→ {model} | {label} critique ({len(draft)} chars)[/dim]\n")
    result = ask_model(prompt, model=model, temperature=temperature)

    if raw or diff_mode:
        click.echo(result["text"])
    else:
        console.print(Markdown(result["text"]))

    if result["input_tokens"] and result.get("cost"):
        console.print(
            f"\n[dim]tokens: {result['input_tokens']} in, "
            f"{result['output_tokens']} out | "
            f"cost: ~${result['cost']:.4f}[/dim]"
        )


if __name__ == "__main__":
    main()
