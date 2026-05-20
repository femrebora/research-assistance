"""Rewriter agent — Claude revises draft based on assessment."""
from __future__ import annotations

from agentic.bridge import call_agent
from agentic.prompts.rewriter import SYSTEM, build_prompt


def run_rewriter(state: dict) -> dict:
    """Rewrite the draft addressing the assessor's critique."""
    prompt = build_prompt(
        draft=state.get("draft", ""),
        assessment=state.get("assessment", {}),
        ai_tells=state.get("ai_tells"),
    )

    result = call_agent(prompt=prompt, model="claude", system=SYSTEM, temperature=0.3)

    return {
        "draft": result["text"],
        "text_rewrite_count": state.get("text_rewrite_count", 0) + 1,
        "agent_calls": [{
            "agent": "rewriter",
            "model": "claude",
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "cost": result["cost"],
        }],
    }
