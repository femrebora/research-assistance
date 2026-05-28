"""AI Artifact Detector agent — Gemini researches AI text tells."""
from __future__ import annotations

import json
from datetime import date

from agentic.bridge import call_agent, save_cache, CACHE_DIR
from agentic.prompts.ai_artifacts import SYSTEM, build_prompt

TELLS_CACHE_PATH = str(CACHE_DIR / "ai_tells.json")


def run_ai_artifact_detector(state: dict) -> dict:
    """Research AI text artifacts and cache as ai_tells.json."""
    prompt = build_prompt()
    result = call_agent(prompt=prompt, model="gemini", system=SYSTEM, temperature=0.2)

    text = result["text"].strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        ai_tells = json.loads(text)
    except json.JSONDecodeError:
        ai_tells = {"error": "Failed to parse AI tells JSON", "raw": result["text"]}

    ai_tells["last_updated"] = date.today().isoformat()

    save_cache(TELLS_CACHE_PATH, json.dumps(ai_tells, indent=2))

    return {
        "ai_tells": ai_tells,
        "agent_calls": [{
            "agent": "ai_artifact_detector",
            "model": "gemini",
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "cost": result["cost"],
        }],
    }
