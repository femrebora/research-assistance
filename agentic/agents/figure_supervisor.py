"""Figure Supervisor agent — Claude reviews figure quality."""
from __future__ import annotations

import json

from agentic.bridge import call_agent
from agentic.prompts.figure_supervisor import SYSTEM, build_prompt


def run_figure_supervisor(state: dict) -> dict:
    """Review generated figures for publication quality."""
    figures = state.get("figures") or []
    if not figures:
        return {
            "agent_calls": [{
                "agent": "figure_supervisor",
                "model": "claude",
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0,
            }],
        }

    prompt = build_prompt(figures)

    result = call_agent(prompt=prompt, model="claude", system=SYSTEM, temperature=0.2)

    text = result["text"].strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        review = json.loads(text)
    except json.JSONDecodeError:
        review = {"error": "Failed to parse review JSON", "raw": result["text"]}

    updated_figures = []
    if isinstance(review, dict) and "figures" in review:
        for fr in review["figures"]:
            idx = fr.get("index", 0)
            if idx < len(figures):
                f = dict(figures[idx])
                f["review"] = fr
                updated_figures.append(f)
    else:
        updated_figures = list(figures)

    if not updated_figures:
        updated_figures = figures

    return {
        "figures": updated_figures,
        "figure_rewrite_count": state.get("figure_rewrite_count", 0) + 1,
        "agent_calls": [{
            "agent": "figure_supervisor",
            "model": "claude",
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "cost": result["cost"],
        }],
    }
