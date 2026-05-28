"""Assessor agent — Claude evaluates draft quality and AI artifacts."""
from __future__ import annotations

import json
import re

from agentic.bridge import call_agent
from agentic.prompts.assessor import SYSTEM, build_prompt


def _extract_json(text: str) -> dict | None:
    """Extract a JSON object from text that may have surrounding commentary.

    Tries in order:
    1. Direct parse of the full text.
    2. Find the outermost { ... } pair via brace matching.
    3. Find any { ... } pair that parses as JSON.
    """
    text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find outermost { ... } via brace matching
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start:i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    break

    # Fallback: find all { ... } pairs and try each
    for match in re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text):
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            continue

    return None


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
