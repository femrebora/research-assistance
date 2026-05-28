#!/usr/bin/env python3
"""run_review.py — PaperForge for literature review articles.

The pipeline does its OWN web research via DuckDuckGo — no pre-compiled
research file needed. Just provide a topic.

Usage:
    ./run_review.py --topic "Personalized Medicine: AI and Multi-Omics Integration"
    ./run_review.py --topic "CRISPR-Based Therapeutics" --output /tmp/crispr-paper
"""
from __future__ import annotations

import json
from pathlib import Path

import click

from agentic.state import make_initial_state
from agentic.orchestrator import load_caches


@click.command()
@click.option("--topic", "-t", required=True, help="Research topic for the review article.")
@click.option("--output", "-o", help="Output directory (default: ~/thesis/output/review-<slug>).")
@click.option("--max-rewrites", default=3, type=int, help="Max rewrite cycles.")
def main(topic, output, max_rewrites):
    """Generate a review article — the pipeline does its own web research."""
    import agentic.orchestrator as orch
    orch.MIN_SECTION_SCORE = 7

    if not output:
        slug = topic.lower().replace(" ", "-").replace(":", "")[:40]
        from common import THESIS_ROOT
        output = str(THESIS_ROOT / "output" / f"review-{slug}")

    click.echo(f"Topic: {topic}")
    click.echo(f"Output: {output}\n")

    click.echo("Loading knowledge caches...")
    state = make_initial_state(
        code_path="",
        user_summary=topic,
        output_dir=str(Path(output).expanduser().resolve()),
        max_rewrites=max_rewrites,
    )
    state["research_topic"] = topic
    state["review_mode"] = True

    cache_updates = load_caches(state)
    state.update(cache_updates)

    if state.get("style_guide"):
        click.echo("  ✓ style_guide.md loaded")
    if state.get("ai_tells"):
        click.echo(f"  ✓ ai_tells.json loaded ({len(state['ai_tells'].get('overused_words', []))} words)")

    click.echo("\nBuilding pipeline (review mode)...")
    graph = _build_review_graph()

    click.echo("Running pipeline...\n")
    final_state = graph.invoke(state)

    out_dir = Path(state["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    if final_state.get("draft"):
        draft_path = out_dir / "paper.md"
        draft_path.write_text(final_state["draft"], encoding="utf-8")
        click.echo(f"  ✓ Draft saved: {draft_path}")

    if final_state.get("assessment"):
        assess_path = out_dir / "assessment.json"
        assess_path.write_text(json.dumps(final_state["assessment"], indent=2), encoding="utf-8")
        click.echo(f"  ✓ Assessment saved: {assess_path}")

    if final_state.get("originality_score"):
        score_path = out_dir / "originality.json"
        score_path.write_text(json.dumps(final_state["originality_score"], indent=2), encoding="utf-8")
        click.echo(f"  ✓ Originality report: {score_path}")

    agent_calls = final_state.get("agent_calls", [])
    total_cost = sum(c.get("cost", 0) or 0 for c in agent_calls)
    click.echo(f"\n{'='*50}")
    click.echo("Pipeline complete.")
    click.echo(f"  Agent calls: {len(agent_calls)}")
    click.echo(f"  Text rewrites: {final_state.get('text_rewrite_count', 0)}")
    click.echo(f"  Figure rewrites: {final_state.get('figure_rewrite_count', 0)}")
    click.echo(f"  Estimated cost: ${total_cost:.4f}")
    click.echo(f"  Output: {out_dir}")


def _build_review_graph():
    """Build a pipeline for review articles (literature research → paper)."""
    from langgraph.graph import StateGraph, END
    from agentic.state import PaperState
    from agentic.agents import (
        run_writer,
        run_assessor,
        run_rewriter,
        run_plagiarism_check,
        run_figure_gen,
        run_figure_supervisor,
    )
    from agentic.agents.literature_researcher import run_literature_researcher
    from agentic.orchestrator import (
        _should_rewrite,
        _should_regenerate_figure,
        _collect_agent_calls,
        _log,
    )

    builder = StateGraph(PaperState)

    def lit_wrapper(state: dict) -> dict:
        _log("Literature Researcher", "searching web & synthesizing...")
        return _collect_agent_calls(state, run_literature_researcher(state))

    def writer_wrapper(state: dict) -> dict:
        _log("Writer (DeepSeek)", "generating review draft...")
        return _collect_agent_calls(state, run_writer(state))

    def assessor_wrapper(state: dict) -> dict:
        _log("Assessor (Claude)", "evaluating draft...")
        return _collect_agent_calls(state, run_assessor(state))

    def rewriter_wrapper(state: dict) -> dict:
        n = state.get("text_rewrite_count", 0) + 1
        _log(f"Rewriter (Claude)", f"revision #{n}...")
        return _collect_agent_calls(state, run_rewriter(state))

    def plagiarism_wrapper(state: dict) -> dict:
        _log("Plagiarism Check (DeepSeek)", "checking originality...")
        return _collect_agent_calls(state, run_plagiarism_check(state))

    def figure_gen_wrapper(state: dict) -> dict:
        n = state.get("figure_rewrite_count", 0) + 1
        _log(f"Figure Gen (Gemini)", f"generating figures (#{n})...")
        return _collect_agent_calls(state, run_figure_gen(state))

    def figure_supervisor_wrapper(state: dict) -> dict:
        _log("Figure Supervisor (Claude)", "reviewing figures...")
        return _collect_agent_calls(state, run_figure_supervisor(state))

    builder.add_node("literature_researcher", lit_wrapper)
    builder.add_node("writer", writer_wrapper)
    builder.add_node("assessor", assessor_wrapper)
    builder.add_node("rewriter", rewriter_wrapper)
    builder.add_node("plagiarism_check", plagiarism_wrapper)
    builder.add_node("figure_gen", figure_gen_wrapper)
    builder.add_node("figure_supervisor", figure_supervisor_wrapper)

    builder.set_entry_point("literature_researcher")
    builder.add_edge("literature_researcher", "writer")
    builder.add_edge("writer", "assessor")

    builder.add_conditional_edges("assessor", _should_rewrite, {
        "rewrite": "rewriter",
        "pass": "plagiarism_check",
    })
    builder.add_edge("rewriter", "assessor")
    builder.add_edge("plagiarism_check", "figure_gen")
    builder.add_edge("figure_gen", "figure_supervisor")
    builder.add_conditional_edges("figure_supervisor", _should_regenerate_figure, {
        "regenerate": "figure_gen",
        "pass": END,
    })

    return builder.compile()


if __name__ == "__main__":
    main()
