#!/usr/bin/env python3
"""run_agentic.py — entry point for the PaperForge agentic pipeline.

Usage:
    ./run_agentic.py /path/to/code --summary "My project does X" --output /path/to/output
    ./run_agentic.py --refresh-style
    ./run_agentic.py --refresh-artifacts
    ./run_agentic.py --ui
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from agentic.state import make_initial_state
from agentic.orchestrator import build_graph, load_caches
from agentic.agents.style_researcher import run_style_researcher
from agentic.agents.ai_artifact_detector import run_ai_artifact_detector
from common import THESIS_ROOT


@click.command()
@click.argument("code_path", required=False)
@click.option("--summary", "-s", help="One-paragraph project summary.")
@click.option("--output", "-o", default=str(THESIS_ROOT / "output"),
              help="Output directory for generated paper.")
@click.option("--min-score", default=7, type=int, help="Minimum section score (1-10).")
@click.option("--max_rewrites", default=3, type=int, help="Max rewrite cycles per loop.")
@click.option("--refresh-style", is_flag=True, help="Regenerate the academic style guide cache.")
@click.option("--refresh-artifacts", is_flag=True, help="Regenerate the AI artifacts cache.")
@click.option("--ui", "launch_ui", is_flag=True, help="Launch the Streamlit web UI.")
@click.option("--domain", default="bioinformatics", help="Academic domain for style research.")
def main(code_path, summary, output, min_score, max_rewrites, refresh_style, refresh_artifacts, launch_ui, domain):
    """PaperForge — multi-agent academic paper generation."""
    import agentic.orchestrator as orch
    orch.MIN_SECTION_SCORE = min_score

    if launch_ui:
        import subprocess
        ui_path = Path(__file__).parent / "agentic" / "ui" / "dashboard.py"
        subprocess.run(["streamlit", "run", str(ui_path)])
        return

    if refresh_style:
        click.echo("Regenerating academic style guide...")
        delta = run_style_researcher({"domain": domain, "agent_calls": []})
        click.echo(f"Done. {len(delta['style_guide'])} characters written.")
        return

    if refresh_artifacts:
        click.echo("Researching AI text artifacts...")
        delta = run_ai_artifact_detector({"agent_calls": []})
        click.echo(f"Done. {len(delta['ai_tells'].get('overused_words', []))} overused words found.")
        return

    if not code_path or not summary:
        click.echo("Error: CODE_PATH and --summary required for pipeline run.\n")
        click.echo("Example: ./run_agentic.py /path/to/code --summary 'My project' --output /tmp/out")
        sys.exit(1)

    click.echo("Loading knowledge caches...")
    state = make_initial_state(
        code_path=str(Path(code_path).expanduser().resolve()),
        user_summary=summary,
        output_dir=str(Path(output).expanduser().resolve()),
        max_rewrites=max_rewrites,
    )
    cache_updates = load_caches(state)
    state.update(cache_updates)

    if state.get("style_guide"):
        click.echo("  ✓ style_guide.md loaded from cache")
    else:
        click.echo("  ⚠ No style guide cache. Run --refresh-style first.")

    if state.get("ai_tells"):
        click.echo(f"  ✓ ai_tells.json loaded ({len(state['ai_tells'].get('overused_words', []))} overused words tracked)")
    else:
        click.echo("  ⚠ No AI tells cache. Run --refresh-artifacts first.")

    click.echo("\nBuilding LangGraph pipeline...")
    graph = build_graph()

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


if __name__ == "__main__":
    main()
