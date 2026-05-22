#!/usr/bin/env python3
"""pipeline.py — full thesis-paragraph orchestrator.

The 6-step chain described in `my_request`:

  1. Retrieve context from your Zotero/RAG index.
  2. Ask Writer model to draft a paragraph grounded in the retrieved sources.
  3. Ask Paraphraser model to rewrite the draft in fresh academic prose.
  4. Ask Critic model to critique remaining issues + unsupported claims.
  5. Run citation verifier (citekey hygiene against bib/thesis.bib).
  6. Save the AI usage log entry (every model call is already logged by common.py).

Every stage logs to ~/thesis/logs/YYYY-MM-DD.jsonl automatically, so step 6
is implicit. This script also writes a per-run markdown report.

Usage:
    ./pipeline.py "What is NUMT contamination?" \\
        --writer claude --paraphraser gemini --critic gpt --checker sonnet \\
        --save outputs/numt_run.md

    ./pipeline.py "..." --writer claude --paraphraser gemini --critic gpt \\
        --no-verify    # skip the citation verifier step
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from common import MODELS, ask_model, save_file, THESIS_ROOT

console = Console()


WRITER_PROMPT = """You are drafting one paragraph for a master's thesis.

## Question / job
{question}

## Retrieved sources (cite with [@citekey])
{context}

## Your task
Write ONE academic paragraph (140–220 words) answering the question, grounded
entirely in the retrieved sources. Cite every factual claim. Do not invent
citations. Formal academic register, no bullets, no headings.
"""

PARAPHRASER_PROMPT = """Rewrite the following paragraph in fresh academic prose.

Constraints:
- Preserve every factual claim. Do not add new claims.
- Preserve every [@citekey] citation in its original anchoring sentence.
- Change sentence structure and word choice. No synonym-swap-only edits.
- Same length (±20%). One paragraph. No bullets or headings.
- Output ONLY the paraphrased paragraph.

## Original
{draft}
"""

CRITIC_PROMPT = """Critique this paragraph. Do NOT rewrite it.

## Question / job
{question}

## Paragraph
{paragraph}

Cover: clarity, argument support, citation gaps, committee challenges,
overreach, structure. Be terse, numbered list. End with one line:
VERDICT: ACCEPT, REVISE, or REJECT.
"""


@dataclass(frozen=True)
class PipelineStep:
    name: str
    text: str
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost: Optional[float] = None


def _retrieve_context(question: str, k: int, threshold: float) -> tuple[str, list[dict]]:
    """Step 1: RAG retrieval. Returns (context_block, retrieved_chunks)."""
    try:
        from researcher import (
            _get_collection,
            build_context,
            deduplicate_by_source,
            retrieve_chunks,
        )
    except ImportError as e:
        raise RuntimeError(f"researcher.py is required for retrieval: {e}") from e

    collection = _get_collection()
    chunks = retrieve_chunks(question, collection=collection, k=k, threshold=threshold)
    deduped = deduplicate_by_source(chunks) if chunks else []
    return build_context(deduped), deduped


def _run_model_step(name: str, prompt: str, model: str, temperature: float) -> PipelineStep:
    console.print(f"[dim]→ [{name}] {model} ({MODELS[model]})[/dim]")
    result = ask_model(prompt, model=model, temperature=temperature)
    return PipelineStep(
        name=name,
        text=result["text"].strip(),
        model=MODELS[model],
        input_tokens=result.get("input_tokens"),
        output_tokens=result.get("output_tokens"),
        cost=result.get("cost"),
    )


def _run_verifier(paragraph: str, bib_path: str) -> PipelineStep:
    """Step 5: run citation verifier inline (no subprocess)."""
    from verify import extract_bib_keys, extract_draft_keys
    from common import read_file

    try:
        bib_text = read_file(bib_path)
    except FileNotFoundError:
        return PipelineStep(
            name="verify",
            text=f"Bibliography not found at {bib_path}; verifier skipped.",
        )

    draft_keys = extract_draft_keys(paragraph)
    bib_keys = extract_bib_keys(bib_text)
    if not draft_keys:
        return PipelineStep(name="verify", text="No [@citekey] citations found in paragraph.")

    missing = sorted({k for k in draft_keys if k not in bib_keys})
    resolved = sorted({k for k in draft_keys if k in bib_keys})

    lines = [f"Citations in paragraph: {len(draft_keys)} ({len(set(draft_keys))} unique)"]
    lines.append(f"Resolved against {bib_path}: {len(resolved)}")
    if missing:
        lines.append(f"Missing: {len(missing)} — {', '.join(missing)}")
    else:
        lines.append("All citations resolved.")
    return PipelineStep(name="verify", text="\n".join(lines))


def run_pipeline(
    question: str,
    writer: str,
    paraphraser: str,
    critic: str,
    k: int = 12,
    threshold: float = 0.30,
    temperature: float = 0.3,
    verify_bib: Optional[str] = "bib/thesis.bib",
) -> list[PipelineStep]:
    """Execute the 6-step chain. Returns one PipelineStep per executed stage."""
    console.print(f"[bold cyan]Step 1/5: retrieve[/bold cyan]")
    context, chunks = _retrieve_context(question, k=k, threshold=threshold)
    n_chunks = len(chunks)
    retrieve_step = PipelineStep(
        name="retrieve",
        text=f"Retrieved {n_chunks} chunks (k={k}, threshold={threshold}).\n\n{context}",
    )

    if n_chunks == 0:
        console.print("[yellow]No sources retrieved. Aborting pipeline.[/yellow]")
        return [retrieve_step]

    console.print(f"[bold cyan]Step 2/5: writer[/bold cyan]")
    writer_step = _run_model_step(
        "writer",
        WRITER_PROMPT.format(question=question, context=context),
        writer,
        temperature,
    )

    console.print(f"[bold cyan]Step 3/5: paraphraser[/bold cyan]")
    para_step = _run_model_step(
        "paraphraser",
        PARAPHRASER_PROMPT.format(draft=writer_step.text),
        paraphraser,
        temperature,
    )

    console.print(f"[bold cyan]Step 4/5: critic[/bold cyan]")
    critic_step = _run_model_step(
        "critic",
        CRITIC_PROMPT.format(question=question, paragraph=para_step.text),
        critic,
        0.2,
    )

    steps = [retrieve_step, writer_step, para_step, critic_step]

    if verify_bib:
        console.print(f"[bold cyan]Step 5/5: verify (citekeys vs {verify_bib})[/bold cyan]")
        steps.append(_run_verifier(para_step.text, verify_bib))

    return steps


def format_report(question: str, steps: list[PipelineStep]) -> str:
    parts = [
        f"# Pipeline run\n",
        f"_Timestamp: {datetime.now(tz=timezone.utc).isoformat()}_\n",
        f"## Question / job\n\n{question}\n",
    ]
    for s in steps:
        title = f"## {s.name.title()}"
        if s.model:
            title += f" — {s.model}"
        parts.append(title + "\n")
        parts.append(s.text + "\n")

    total_in = sum((s.input_tokens or 0) for s in steps)
    total_out = sum((s.output_tokens or 0) for s in steps)
    total_cost = sum((s.cost or 0.0) for s in steps)
    parts.append(
        f"---\n\n_total tokens: {total_in} in / {total_out} out · "
        f"estimated cost: ${total_cost:.4f}_\n"
    )
    parts.append(
        "_Per-call disclosure log: "
        f"`{(THESIS_ROOT / 'logs').as_posix()}/YYYY-MM-DD.jsonl`._\n"
    )
    return "\n".join(parts)


@click.command()
@click.argument("question")
@click.option("--writer", "-w", required=True,
              type=click.Choice(list(MODELS.keys())),
              help="Model that drafts the paragraph from retrieved sources.")
@click.option("--paraphraser", "-p", required=True,
              type=click.Choice(list(MODELS.keys())),
              help="Model that rewrites the draft in fresh prose.")
@click.option("--critic", "-c", required=True,
              type=click.Choice(list(MODELS.keys())),
              help="Model that critiques the paraphrased paragraph.")
@click.option("--k", "-k", default=12, type=int, help="RAG chunks to retrieve.")
@click.option("--threshold", "-t", default=0.30, type=float, help="Similarity threshold (0-1).")
@click.option("--temperature", default=0.3, type=float, help="Writer/paraphraser temperature.")
@click.option("--bib", default="bib/thesis.bib", help="Bibliography for citation verifier.")
@click.option("--no-verify", is_flag=True, help="Skip the citation verifier step.")
@click.option("--save", "-o", default=None, help="Save the full report to this path.")
@click.option("--raw", is_flag=True, help="Plain text output instead of rendered panels.")
def main(question, writer, paraphraser, critic, k, threshold, temperature, bib, no_verify, save, raw):
    """Full pipeline: retrieve → draft → paraphrase → critique → verify → log."""
    try:
        steps = run_pipeline(
            question=question,
            writer=writer,
            paraphraser=paraphraser,
            critic=critic,
            k=k,
            threshold=threshold,
            temperature=temperature,
            verify_bib=None if no_verify else bib,
        )
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    report = format_report(question, steps)

    if save:
        path = save_file(save, report)
        console.print(f"\n[green]Pipeline report saved to: {path}[/green]\n")

    if raw:
        click.echo(report)
        return

    # Render each model-output step as a panel; retrieve + verify shown plainly.
    for s in steps:
        if s.name in ("retrieve", "verify"):
            console.print(Panel(s.text, title=s.name, border_style="dim"))
        else:
            console.print(Panel(Markdown(s.text), title=f"{s.name} — {s.model}", border_style="cyan"))

    summary = Table(title="Stage costs", show_lines=False)
    summary.add_column("Stage", style="cyan")
    summary.add_column("Model", style="dim")
    summary.add_column("In", justify="right")
    summary.add_column("Out", justify="right")
    summary.add_column("Cost (USD)", justify="right")
    for s in steps:
        if s.model:
            summary.add_row(
                s.name,
                s.model,
                str(s.input_tokens or 0),
                str(s.output_tokens or 0),
                f"${(s.cost or 0):.4f}",
            )
    console.print(summary)


if __name__ == "__main__":
    main()
