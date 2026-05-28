"""Assessor agent — Claude evaluates draft quality and AI artifacts."""
from __future__ import annotations

import json

from agentic.bridge import call_agent
from agentic.prompts.assessor import SYSTEM, build_prompt


def _extract_json(text: str) -> dict | None:
    """Extract a JSON object from text that may have surrounding commentary.

    Uses json.JSONDecoder().raw_decode which correctly handles braces
    inside string literals and nested structures.
    """
    text = text.strip()
    start = 0
    while True:
        start = text.find("{", start)
        if start == -1:
            return None
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[start:])
            if isinstance(obj, dict):
                return obj
            start += 1
        except json.JSONDecodeError:
            start += 1


def run_assessor(state: dict) -> dict:
    """Evaluate the draft and return structured scores."""
    prompt = build_prompt(
        draft=state.get("draft", ""),
        ai_tells=state.get("ai_tells"),
    )

    result = call_agent(prompt=prompt, model="claude", system=SYSTEM, temperature=0.2)

    text = result["text"].strip()

    # Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Extract JSON from surrounding commentary
    assessment = _extract_json(text)
    if assessment is None:
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
