"""Writer agent — DeepSeek generates the paper draft."""
from __future__ import annotations

from agentic.benchmark_parser import parse_benchmarks
from agentic.bridge import call_agent
from agentic.prompts.writer import SYSTEM, build_prompt
from agentic.text_cleanup import cleanup_prose


def run_writer(state: dict) -> dict:
    """Generate a complete paper draft from technical report and style guide."""
    benchmark_data = state.get("benchmark_data", "")
    if not benchmark_data:
        code_path = state.get("code_path", "")
        if code_path:
            benchmark_data = parse_benchmarks(code_path)

    prompt = build_prompt(
        technical_report=state.get("technical_report", ""),
        style_guide=state.get("style_guide", ""),
        user_summary=state.get("user_summary", ""),
        rag_context=state.get("rag_context", ""),
        ai_tells=state.get("ai_tells"),
        benchmark_data=benchmark_data,
    )

    result = call_agent(prompt=prompt, model="deepseek", system=SYSTEM, temperature=0.6)
    draft = cleanup_prose(result["text"])

    return {
        "draft": draft,
        "agent_calls": [{
            "agent": "writer",
            "model": "deepseek",
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "cost": result["cost"],
        }],
    }
