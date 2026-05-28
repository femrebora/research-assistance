"""Academic Style Researcher agent — DeepSeek analyzes domain writing patterns."""
from __future__ import annotations

from agentic.bridge import call_agent, save_cache, CACHE_DIR
from agentic.prompts.style_researcher import SYSTEM, build_prompt

STYLE_CACHE_PATH = str(CACHE_DIR / "style_guide.md")


def run_style_researcher(state: dict) -> dict:
    """Generate or load the academic style guide. Cached per domain."""
    domain = state.get("domain", "bioinformatics")

    prompt = build_prompt(domain=domain)
    result = call_agent(prompt=prompt, model="deepseek", system=SYSTEM, temperature=0.3)
    style_guide = result["text"]

    save_cache(STYLE_CACHE_PATH, style_guide)

    return {
        "style_guide": style_guide,
        "agent_calls": [{
            "agent": "style_researcher",
            "model": "deepseek",
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "cost": result["cost"],
        }],
    }
