"""Assessor agent — Claude evaluates draft quality and AI artifacts."""
from __future__ import annotations

import json

from agentic.bridge import call_agent
from agentic.prompts.assessor import SYSTEM, build_prompt


def run_assessor(state: dict) -> dict:
    """Evaluate the draft and return structured scores."""
    prompt = build_prompt(
        draft=state.get("draft", ""),
        ai_tells=state.get("ai_tells"),
    )

    result = call_agent(prompt=prompt, model="claude", system=SYSTEM, temperature=0.2)

    text = result["text"].strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        assessment = json.loads(text)
    except json.JSONDecodeError:
        assessment = {"error": "Failed to parse assessment JSON", "raw": result["text"]}

    return {
        "assessment": assessment,
        "agent_calls": [{
            "agent": "assessor",
            "model": "claude",
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "cost": result["cost"],
        }],
    }
