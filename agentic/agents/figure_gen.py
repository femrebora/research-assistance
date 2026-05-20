"""Figure Generator agent — Gemini creates matplotlib visualization code."""
from __future__ import annotations

import re

from agentic.bridge import call_agent
from agentic.prompts.figure_gen import SYSTEM, build_prompt


def run_figure_gen(state: dict) -> dict:
    """Generate matplotlib figures from technical context."""
    prompt = build_prompt(
        technical_report=state.get("technical_report", ""),
        code_path=state.get("code_path", ""),
        figure_descriptions=state.get("figure_descriptions",
            "Generate 3–5 figures appropriate for a bioinformatics methods paper based on the technical report. "
            "Include: 1) a pipeline/workflow diagram, 2) a performance benchmark comparison (boxplot or bar chart), "
            "3) an accuracy or runtime analysis plot."),
    )

    result = call_agent(prompt=prompt, model="gemini", system=SYSTEM, temperature=0.3)

    text = result["text"]
    figure_blocks = re.findall(r"###\s*(Figure \d+:.*?)\n```python\n(.*?)```", text, re.DOTALL)

    figures = []
    for title, code in figure_blocks:
        figures.append({
            "title": title.strip(),
            "code": code.strip(),
            "png_path": None,
            "review": None,
        })

    if not figures:
        figures = [{"title": "figures", "code": text, "png_path": None, "review": None}]

    return {
        "figures": figures,
        "agent_calls": [{
            "agent": "figure_gen",
            "model": "gemini",
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "cost": result["cost"],
        }],
    }
