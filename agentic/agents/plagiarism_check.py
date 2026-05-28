"""Plagiarism + AI Checker agent — DeepSeek evaluates originality."""
from __future__ import annotations

import json

from agentic.bridge import call_agent
from agentic.prompts.plagiarism import SYSTEM, build_prompt


def run_plagiarism_check(state: dict) -> dict:
    """Check the draft for originality and AI-generated patterns."""
    prompt = build_prompt(
        text=state.get("draft", ""),
        ai_tells=state.get("ai_tells"),
    )

    result = call_agent(prompt=prompt, model="deepseek", system=SYSTEM, temperature=0.1)

    text = result["text"].strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        score = json.loads(text)
    except json.JSONDecodeError:
        score = {"error": "Failed to parse", "raw": result["text"]}

    return {
        "originality_score": score,
        "agent_calls": [{
            "agent": "plagiarism_check",
            "model": "deepseek",
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "cost": result["cost"],
        }],
    }
