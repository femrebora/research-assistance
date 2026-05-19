#!/usr/bin/env python3
"""compare.py — ask the same question to multiple AI models and compare answers.

Two modes:
  1. RAG mode (with --rag): retrieves context from your indexed Zotero PDFs,
     then sends identical context to each model. Get a second/third opinion
     on the same evidence.
  2. Direct mode (default): sends the question directly to each model without
     document context. Useful for quick cross-model sanity checks.

Usage:
    ./compare.py "What are the main approaches to NUMT filtering?" --models claude,gemini,gpt
    ./compare.py "..." --models claude,gemini --rag --k 15
    ./compare.py "..." --models claude,deepseek,gpt --save comparison_session
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import click
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from common import MODELS, ask_model

console = Console()


def _call_model(
    question: str,
    model: str,
    system: Optional[str] = None,
    temperature: float = 0.3,
) -> dict:
    """Call a single model and return result dict. Handles errors gracefully."""
    try:
        result = ask_model(
            question,
            model=model,
            system=system,
            temperature=temperature,
        )
        return {
            "answer": result["text"],
            "model": MODELS.get(model, model),
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
            "cost": result.get("cost", 0.0),
            "error": None,
        }
    except Exception as e:
        return {
            "answer": f"Error: {e}",
            "model": MODELS.get(model, model),
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
            "error": str(e),
        }


def compare_direct(
    question: str,
    models: list[str],
    system: Optional[str] = None,
    temperature: float = 0.3,
) -> dict[str, dict]:
    """Compare model answers without RAG context (direct question)."""
    console.print(f"[dim]→ Comparing {len(models)} models directly (no document context)[/dim]\n")

    outcomes: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=len(models)) as executor:
        futures = {
            executor.submit(_call_model, question, m, system, temperature): m
            for m in models
        }
        for future in as_completed(futures):
            model = futures[future]
            outcomes[model] = future.result()
            status = "[red]✗[/red]" if outcomes[model]["error"] else "[green]✓[/green]"
            console.print(f"  {status} {model}")

    return outcomes


def compare_rag(
    question: str,
    models: list[str],
    temperature: float = 0.3,
    k: int = 20,
    threshold: float = 0.35,
    embedding_model: str = "openai/text-embedding-3-small",
) -> dict[str, dict]:
    """Compare model answers with RAG context from indexed Zotero PDFs."""
    try:
        from researcher import compare_research_question
    except ImportError:
        console.print("[red]Cannot import researcher.py. Make sure it's in the same directory.[/red]")
        sys.exit(1)

    return compare_research_question(
        question=question,
        models=models,
        temperature=temperature,
        k=k,
        threshold=threshold,
        embedding_model=embedding_model,
    )


def build_comparison_table(outcomes: dict[str, dict], question: str) -> Table:
    """Build a Rich table showing model comparison."""
    table = Table(title=f"Comparison: {question[:80]}...", show_lines=True)
    table.add_column("Model", style="cyan bold", width=12, no_wrap=True)
    table.add_column("Answer", style="white", width=55)
    table.add_column("Tokens", style="dim", width=14)
    table.add_column("Cost", style="dim", width=10)

    for model_name, r in outcomes.items():
        answer = (r.get("answer", "") or "")
        answer_text = answer[:500]
        if len(answer) > 500:
            answer_text += " [...truncated]"

        tokens_str = f"{r.get('input_tokens', '?')}/{r.get('output_tokens', '?')}"
        cost_str = f"${r['cost']:.4f}" if r.get("cost") else "?"

        table.add_row(model_name, answer_text, tokens_str, cost_str)

    total_cost = sum(r.get("cost", 0) or 0 for r in outcomes.values())
    if total_cost:
        table.caption = f"Total cost: ${total_cost:.4f}"

    return table


@click.command()
@click.argument("question")
@click.option(
    "--models", "-m",
    required=True,
    help="Comma-separated model names, e.g. 'claude,gemini,deepseek,gpt'.",
)
@click.option(
    "--rag", is_flag=True,
    help="Use RAG context from indexed Zotero PDFs (requires researcher.py index first).",
)
@click.option(
    "--k", "-k", default=20, type=int,
    help="Chunks to retrieve (RAG mode only).",
)
@click.option(
    "--threshold", "-t", default=0.35, type=float,
    help="Similarity threshold 0-1 (RAG mode only).",
)
@click.option(
    "--temperature", default=0.3, type=float,
    help="LLM temperature.",
)
@click.option(
    "--system", "-s", default=None,
    help="Optional system prompt (direct mode only).",
)
@click.option(
    "--save", "-o", default=None,
    help="Save comparison to session file.",
)
@click.option("--raw", is_flag=True, help="Print raw text instead of rendered panels.")
def main(question, models, rag, k, threshold, temperature, system, save, raw):
    """Compare answers from multiple AI models to the same question."""

    model_list = [m.strip() for m in models.split(",") if m.strip() in MODELS]
    invalid = [m.strip() for m in models.split(",") if m.strip() not in MODELS]
    if invalid:
        console.print(f"[red]Unknown models: {', '.join(invalid)}[/red]")
        console.print(f"[dim]Available: {', '.join(MODELS.keys())}[/dim]")
        sys.exit(1)

    if not model_list:
        console.print(f"[red]No valid models specified. Available: {', '.join(MODELS.keys())}[/red]")
        sys.exit(1)

    if rag:
        outcomes = compare_rag(
            question=question,
            models=model_list,
            temperature=temperature,
            k=k,
            threshold=threshold,
        )
    else:
        outcomes = compare_direct(
            question=question,
            models=model_list,
            system=system,
            temperature=temperature,
        )

    # Display
    if raw:
        for model_name, r in outcomes.items():
            click.echo(f"\n=== {model_name} ({r.get('model', '?')}) ===\n")
            click.echo(r.get("answer", ""))
    else:
        table = build_comparison_table(outcomes, question)
        console.print(table)

    # Summary footer
    total_in = sum(r.get("input_tokens", 0) or 0 for r in outcomes.values())
    total_out = sum(r.get("output_tokens", 0) or 0 for r in outcomes.values())
    total_cost = sum(r.get("cost", 0) or 0 for r in outcomes.values())
    console.print(
        f"\n[dim]Total: {total_in} tokens in, {total_out} out | "
        f"Cost: ${total_cost:.4f}[/dim]"
    )

    # Save to session
    if save:
        try:
            from researcher import _save_comparison_session
            _save_comparison_session(save, question, outcomes)
            from researcher import SESSION_DIR
            console.print(f"\n[green]Comparison saved: {SESSION_DIR / f'{save}.md'}[/green]")
        except ImportError:
            console.print("[yellow]Cannot save session: researcher.py not importable[/yellow]")


if __name__ == "__main__":
    main()
