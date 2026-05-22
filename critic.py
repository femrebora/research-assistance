#!/usr/bin/env python3
"""critic.py — writer + critic two-model pipeline.

One model writes a draft paragraph from a job + optional sources, then a
SECOND model critiques the draft. This is different from `critique.py`,
which only critiques text YOU have already written.

Use this to stress-test prompts, scaffold a paragraph before rewriting it,
or get a cross-model adversarial review of an AI-generated draft.

Usage:
    ./critic.py "Define NUMT contamination" --writer claude --critic gpt
    ./critic.py "..." --writer claude --critic gemini --sources evidence/ch1.md
    ./critic.py "..." --writer sonnet --critic claude --save outputs/critic_run.md
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from common import MODELS, ask_model, read_file, save_file

console = Console()


WRITER_PROMPT = """Write ONE academic paragraph (140–220 words) addressing this job.

## Job
{job}
{sources_section}
## Constraints
- Formal academic register. One paragraph. No bullets.
- Cite factual claims with [@citekey] when sources are provided.
- Do NOT invent citations. If sources are absent, write generally without fabricated citations.
"""


CRITIC_PROMPT = """Critique the following draft paragraph. Do NOT rewrite it.

## Job the paragraph must do
{job}

## Draft (written by another model)
{draft}

## Your task
Be specific. Cover:
1. **Clarity** — what is unclear or could be misread?
2. **Argument** — what claim is unsupported, hand-wavy, or overstated?
3. **Citations** — what claim needs a citation but lacks one; which citations look suspect?
4. **Committee challenge** — what would a skeptical thesis committee object to?
5. **Job fit** — does the paragraph actually do the stated job? What's missing?
6. **Structure** — is the order of ideas defensible?

Format as a numbered list under each heading. Be terse. Do NOT provide replacement prose.
End with one line: VERDICT: ACCEPT, REVISE, or REJECT.
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
    blocks = []
    for sp in source_paths:
        try:
            content = read_file(sp)
        except FileNotFoundError:
            console.print(f"[yellow]Source not found: {sp}[/yellow]")
            continue
        blocks.append(f"### Source: {sp}\n\n{content.strip()}\n")
    return "\n".join(blocks)


def _run_stage(label: str, prompt: str, model: str, temperature: float) -> StageResult:
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


def run_critic_pipeline(
    job: str,
    writer: str,
    critic: str,
    sources_text: str = "",
    writer_temperature: float = 0.3,
    critic_temperature: float = 0.2,
) -> list[StageResult]:
    """Run writer → critic. Returns the two stage results."""
    sources_section = (
        f"\n## Sources (cite with [@citekey])\n\n{sources_text}\n"
        if sources_text else ""
    )
    writer_prompt = WRITER_PROMPT.format(job=job, sources_section=sources_section)
    writer_stage = _run_stage("writer", writer_prompt, writer, writer_temperature)

    critic_prompt = CRITIC_PROMPT.format(job=job, draft=writer_stage.text)
    critic_stage = _run_stage("critic", critic_prompt, critic, critic_temperature)

    return [writer_stage, critic_stage]


def format_chain(job: str, stages: list[StageResult]) -> str:
    parts = [f"# Critic pipeline\n\n## Job\n\n{job}\n"]
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
@click.argument("job")
@click.option("--writer", "-w", required=True,
              type=click.Choice(list(MODELS.keys())),
              help="Model that drafts the paragraph.")
@click.option("--critic", "-c", required=True,
              type=click.Choice(list(MODELS.keys())),
              help="Model that critiques the draft.")
@click.option("--sources", "-s", multiple=True,
              help="One or more source files (repeatable).")
@click.option("--writer-temp", default=0.3, type=float, help="Temperature for the writer.")
@click.option("--critic-temp", default=0.2, type=float, help="Temperature for the critic.")
@click.option("--save", "-o", default=None, help="Save the full chain to this path.")
@click.option("--raw", is_flag=True, help="Print plain text instead of rendered panels.")
def main(job, writer, critic, sources, writer_temp, critic_temp, save, raw):
    """Writer + critic: one model drafts, another critiques."""
    sources_text = _load_sources(sources) if sources else ""

    stages = run_critic_pipeline(
        job=job,
        writer=writer,
        critic=critic,
        sources_text=sources_text,
        writer_temperature=writer_temp,
        critic_temperature=critic_temp,
    )

    chain_md = format_chain(job, stages)

    if save:
        path = save_file(save, chain_md)
        console.print(f"[green]Saved chain to: {path}[/green]\n")

    if raw:
        click.echo(chain_md)
        return

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
