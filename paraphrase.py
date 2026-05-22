#!/usr/bin/env python3
"""paraphrase.py — 3-model paraphrase pipeline.

Stages:
  1. Writer drafts an academic paragraph from a brief + optional sources.
  2. Paraphraser rewrites the draft in fresh academic prose.
  3. Checker compares meaning between draft and paraphrase and flags any
     drift, lost citations, or unsupported claims.

Each stage logs its call to ~/thesis/logs/YYYY-MM-DD.jsonl (via common.ask_model)
so the full chain is auditable for AI-usage disclosure.

Usage:
    ./paraphrase.py drafts/para.md \\
        --writer claude \\
        --paraphraser gemini \\
        --checker gpt \\
        --sources evidence/ch1.md

    # Skip the writer stage and paraphrase an existing draft instead:
    ./paraphrase.py drafts/para.md --skip-writer --paraphraser claude --checker gpt

    # Save the full chain (brief, draft, paraphrase, check) to a file:
    ./paraphrase.py drafts/para.md --writer claude --paraphraser gemini \\
        --checker gpt --save outputs/ch1_para.md
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Optional

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from common import MODELS, ask_model, open_in_editor, read_file, save_file

console = Console()


WRITER_PROMPT = """You are drafting one paragraph for a master's thesis.

## Brief
{brief}
{sources_section}
## Your task
Write ONE academic paragraph (120–220 words) addressing the brief above.
- Ground every factual claim in the sources when sources are provided.
- Preserve any [@citekey] citations exactly as written in the sources.
- Do NOT invent citations.
- Use formal academic register. No bullet lists. No headings.
"""


PARAPHRASER_PROMPT = """Rewrite the following paragraph in fresh academic prose.

## Constraints
- Preserve every factual claim. Do not add new claims.
- Preserve every [@citekey] citation in its original anchoring sentence.
- Change sentence structure and word choice; do not paraphrase by synonym-swap.
- Same length (±20%). One paragraph. No bullets, no headings.
- Do NOT include the original; output ONLY the paraphrased paragraph.

## Original paragraph
{draft}
"""


CHECKER_PROMPT = """You are checking semantic equivalence between two paragraphs.

## Original
{draft}

## Paraphrase
{paraphrase}

## Your task
Report any of the following, with sentence-level specifics:

1. **MEANING DRIFT** — claims in the paraphrase that are not in the original
   (or vice versa). Quote the relevant phrase from each side.
2. **LOST CITATIONS** — any [@citekey] present in the original but missing
   from the paraphrase.
3. **NEW CITATIONS** — any [@citekey] in the paraphrase that was not in
   the original.
4. **OVERREACH** — claims that became stronger or weaker in the paraphrase.
5. **VERDICT** — one line: SAFE, MINOR DRIFT, or REJECT.

Be terse. Use a numbered list. If a category has no issues, write "none".
"""


@dataclass(frozen=True)
class StageResult:
    label: str
    model: str
    text: str
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    cost: Optional[float]


def _load_sources(source_paths: tuple[str, ...]) -> str:
    """Concatenate one or more source files into a single context string."""
    blocks = []
    for sp in source_paths:
        try:
            content = read_file(sp)
        except FileNotFoundError:
            console.print(f"[yellow]Source not found: {sp}[/yellow]")
            continue
        blocks.append(f"### Source: {sp}\n\n{content.strip()}\n")
    return "\n".join(blocks)


def _run_stage(
    label: str,
    prompt: str,
    model: str,
    temperature: float,
) -> StageResult:
    console.print(f"[dim]→ {label}: {model} ({MODELS[model]})[/dim]")
    result = ask_model(prompt, model=model, temperature=temperature)
    return StageResult(
        label=label,
        model=MODELS[model],
        text=result["text"].strip(),
        input_tokens=result.get("input_tokens"),
        output_tokens=result.get("output_tokens"),
        cost=result.get("cost"),
    )


def _interactive_stage(
    label: str,
    prompt_builder: Callable[[], str],
    model: str,
    temperature: float,
) -> StageResult:
    """Run a stage with [a]ccept / [e]dit / [r]egenerate / [q]uit loop.

    `prompt_builder` is a zero-arg callable so the prompt can be re-rendered
    on regenerate (no captured-state bugs).
    """
    while True:
        stage = _run_stage(label, prompt_builder(), model, temperature)
        console.print(
            Panel(Markdown(stage.text), title=f"{stage.label} — {stage.model}", border_style="cyan")
        )
        choice = click.prompt(
            f"[{label}] [a]ccept / [e]dit / [r]egenerate / [q]uit",
            type=click.Choice(["a", "e", "r", "q"], case_sensitive=False),
            default="a",
            show_choices=False,
        ).lower()
        if choice == "a":
            return stage
        if choice == "e":
            edited = open_in_editor(stage.text, suffix=f".{label}.md")
            edited = edited.strip()
            if not edited:
                console.print("[yellow]Edited text is empty; keeping the model output.[/yellow]")
                return stage
            console.print(f"[green]✓ {label} edited ({len(edited)} chars accepted)[/green]")
            return replace(stage, text=edited)
        if choice == "r":
            console.print(f"[dim]regenerating {label}...[/dim]")
            continue
        if choice == "q":
            console.print("[yellow]Aborted by user.[/yellow]")
            sys.exit(0)


def run_paraphrase_pipeline(
    brief: str,
    writer: Optional[str],
    paraphraser: str,
    checker: str,
    sources_text: str = "",
    existing_draft: Optional[str] = None,
    temperature: float = 0.3,
    interactive: bool = False,
) -> list[StageResult]:
    """Run writer → paraphraser → checker. Returns one StageResult per stage executed.

    With `interactive=True`, each stage's output is shown and the user can
    [a]ccept / [e]dit (in $EDITOR) / [r]egenerate / [q]uit. The next stage
    consumes whatever text is finally accepted (possibly edited).
    """
    stages: list[StageResult] = []

    def _stage(label, prompt_builder, model, temp):
        if interactive:
            return _interactive_stage(label, prompt_builder, model, temp)
        return _run_stage(label, prompt_builder(), model, temp)

    if existing_draft is not None:
        draft_text = existing_draft.strip()
        if not draft_text:
            raise ValueError("Existing draft is empty.")
    else:
        if writer is None:
            raise ValueError("Either provide an existing draft or specify --writer.")
        sources_section = (
            f"\n## Sources (use these; cite with [@citekey])\n\n{sources_text}\n"
            if sources_text else ""
        )
        writer_prompt = WRITER_PROMPT.format(brief=brief, sources_section=sources_section)
        draft_stage = _stage("writer", lambda: writer_prompt, writer, temperature)
        stages.append(draft_stage)
        draft_text = draft_stage.text

    para_stage = _stage(
        "paraphraser",
        lambda: PARAPHRASER_PROMPT.format(draft=draft_text),
        paraphraser,
        temperature,
    )
    stages.append(para_stage)
    paraphrase_text = para_stage.text

    check_stage = _stage(
        "checker",
        lambda: CHECKER_PROMPT.format(draft=draft_text, paraphrase=paraphrase_text),
        checker,
        0.1,
    )
    stages.append(check_stage)

    return stages


def format_chain(brief: str, stages: list[StageResult]) -> str:
    """Render the full pipeline result as markdown for saving / display."""
    parts = [f"# Paraphrase pipeline\n\n## Brief\n\n{brief}\n"]
    for s in stages:
        parts.append(f"## {s.label.title()} — {s.model}\n\n{s.text}\n")
    total_in = sum((s.input_tokens or 0) for s in stages)
    total_out = sum((s.output_tokens or 0) for s in stages)
    total_cost = sum((s.cost or 0.0) for s in stages)
    parts.append(
        f"---\n\n_tokens: {total_in} in / {total_out} out · "
        f"estimated cost: ${total_cost:.4f}_\n"
    )
    return "\n".join(parts)


@click.command()
@click.argument("brief_or_draft", required=False)
@click.option("--writer", "-w", default=None,
              type=click.Choice(list(MODELS.keys())),
              help="Model that drafts the initial paragraph.")
@click.option("--paraphraser", "-p", required=True,
              type=click.Choice(list(MODELS.keys())),
              help="Model that paraphrases the draft.")
@click.option("--checker", "-c", required=True,
              type=click.Choice(list(MODELS.keys())),
              help="Model that checks meaning between draft and paraphrase.")
@click.option("--sources", "-s", multiple=True,
              help="One or more source files (repeatable). Relative paths resolve against THESIS_ROOT.")
@click.option("--skip-writer", is_flag=True,
              help="Treat BRIEF_OR_DRAFT as an existing draft; skip the writer stage.")
@click.option("--temperature", "-t", default=0.3, type=float,
              help="Model temperature for writer/paraphraser (checker is fixed at 0.1).")
@click.option("--save", "-o", default=None,
              help="Save the full chain (markdown) to this path.")
@click.option("--interactive", "-i", is_flag=True,
              help="Pause between stages: [a]ccept / [e]dit in $EDITOR / [r]egenerate / [q]uit.")
@click.option("--raw", is_flag=True, help="Print plain text instead of rendered markdown panels.")
def main(brief_or_draft, writer, paraphraser, checker, sources, skip_writer, temperature, save, interactive, raw):
    """Three-model paraphrase pipeline: writer → paraphraser → checker."""
    if not brief_or_draft:
        click.echo("Error: provide a brief (writer mode) or a draft path (--skip-writer mode).", err=True)
        sys.exit(1)

    existing_draft: Optional[str] = None
    brief_text = brief_or_draft

    if skip_writer:
        existing_draft = read_file(brief_or_draft)
        brief_text = f"(skip-writer) draft from {brief_or_draft}"
    elif Path(brief_or_draft).expanduser().exists() and writer is None:
        existing_draft = read_file(brief_or_draft)
        brief_text = f"(implicit skip-writer) draft from {brief_or_draft}"
    elif writer is None:
        click.echo("Error: must specify --writer (or use --skip-writer with a draft file).", err=True)
        sys.exit(1)

    sources_text = _load_sources(sources) if sources else ""

    try:
        stages = run_paraphrase_pipeline(
            brief=brief_text,
            writer=writer,
            paraphraser=paraphraser,
            checker=checker,
            sources_text=sources_text,
            existing_draft=existing_draft,
            temperature=temperature,
            interactive=interactive,
        )
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    chain_md = format_chain(brief_text, stages)

    if save:
        path = save_file(save, chain_md)
        console.print(f"[green]Saved chain to: {path}[/green]\n")

    if raw:
        click.echo(chain_md)
        return

    # In interactive mode each stage was already shown during the loop;
    # avoid double-printing.
    if not interactive:
        for s in stages:
            console.print(Panel(Markdown(s.text), title=f"{s.label} — {s.model}", border_style="cyan"))

    total_in = sum((s.input_tokens or 0) for s in stages)
    total_out = sum((s.output_tokens or 0) for s in stages)
    total_cost = sum((s.cost or 0.0) for s in stages)
    console.print(
        f"\n[dim]total: {total_in} tokens in, {total_out} out | "
        f"estimated cost: ${total_cost:.4f}[/dim]"
    )


if __name__ == "__main__":
    main()
