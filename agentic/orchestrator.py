"""LangGraph orchestrator — compiles the paper generation state machine."""
from __future__ import annotations

import json

from langgraph.graph import StateGraph, END

from agentic.state import PaperState
from agentic.agents import (
    run_code_analyst,
    run_style_researcher,
    run_ai_artifact_detector,
    run_writer,
    run_assessor,
    run_rewriter,
    run_plagiarism_check,
    run_figure_gen,
    run_figure_supervisor,
)
from agentic.bridge import is_cache_fresh, load_cache
from agentic.agents.style_researcher import STYLE_CACHE_PATH
from agentic.agents.ai_artifact_detector import TELLS_CACHE_PATH

MIN_SECTION_SCORE = 7
MAX_AI_SOUNDING_SCORE = 3
MIN_ORIGINALITY_PCT = 80
MAX_AI_LIKELIHOOD_PCT = 20


def _should_rewrite(state: dict) -> str:
    """Check if any section scored below threshold."""
    assessment = state.get("assessment") or {}
    rewrite_count = state.get("text_rewrite_count", 0)

    if rewrite_count >= state.get("max_rewrites", 5):
        return "pass"

    for key, section in assessment.items():
        if key in ("overall_notes", "error", "raw"):
            continue
        if isinstance(section, dict):
            score = section.get("score", 0)
            if isinstance(score, (int, float)) and score < MIN_SECTION_SCORE:
                return "rewrite"

    return "pass"


def _should_rewrite_plagiarism(state: dict) -> str:
    """Check if originality is below threshold."""
    score = state.get("originality_score") or {}
    rewrite_count = state.get("text_rewrite_count", 0)

    if rewrite_count >= state.get("max_rewrites", 5):
        return "pass"

    originality = score.get("originality_pct", 100)
    ai_likelihood = score.get("ai_likelihood_pct", 0)

    if originality < MIN_ORIGINALITY_PCT or ai_likelihood > MAX_AI_LIKELIHOOD_PCT:
        return "rewrite"

    return "pass"


def _should_regenerate_figure(state: dict) -> str:
    """Check if figure supervisor found issues."""
    figures = state.get("figures") or []
    rewrite_count = state.get("figure_rewrite_count", 0)

    if rewrite_count >= state.get("max_rewrites", 5):
        return "pass"

    for fig in figures:
        review = fig.get("review") or {}
        if review.get("verdict") == "FAIL":
            return "regenerate"

    return "pass"


def _collect_agent_calls(state: dict, delta: dict) -> dict:
    """Merge agent_calls from a delta into state."""
    existing = list(state.get("agent_calls", []))
    new_calls = delta.get("agent_calls", [])
    merged = {"agent_calls": existing + new_calls}
    for k, v in delta.items():
        if k != "agent_calls":
            merged[k] = v
    return merged


def _log(agent: str, msg: str = "") -> None:
    import sys
    print(f"  [{agent}] {msg}", file=sys.stderr, flush=True)


def build_graph() -> StateGraph:
    """Build and compile the paper generation state machine."""
    builder = StateGraph(PaperState)

    def code_analyst_wrapper(state: dict) -> dict:
        _log("Code Analyst (Gemini)", "analyzing codebase...")
        return _collect_agent_calls(state, run_code_analyst(state))

    def writer_wrapper(state: dict) -> dict:
        _log("Writer (DeepSeek)", "generating paper draft...")
        return _collect_agent_calls(state, run_writer(state))

    def assessor_wrapper(state: dict) -> dict:
        _log("Assessor (Claude)", "evaluating draft...")
        return _collect_agent_calls(state, run_assessor(state))

    def rewriter_wrapper(state: dict) -> dict:
        n = state.get("text_rewrite_count", 0) + 1
        _log(f"Rewriter (Claude)", f"revision #{n}...")
        return _collect_agent_calls(state, run_rewriter(state))

    def plagiarism_wrapper(state: dict) -> dict:
        _log("Plagiarism Check (DeepSeek)", "checking originality...")
        return _collect_agent_calls(state, run_plagiarism_check(state))

    def figure_gen_wrapper(state: dict) -> dict:
        n = state.get("figure_rewrite_count", 0) + 1
        _log(f"Figure Gen (Gemini)", f"generating figures (#{n})...")
        return _collect_agent_calls(state, run_figure_gen(state))

    def figure_supervisor_wrapper(state: dict) -> dict:
        _log("Figure Supervisor (Claude)", "reviewing figures...")
        return _collect_agent_calls(state, run_figure_supervisor(state))

    builder.add_node("code_analyst", code_analyst_wrapper)
    builder.add_node("writer", writer_wrapper)
    builder.add_node("assessor", assessor_wrapper)
    builder.add_node("rewriter", rewriter_wrapper)
    builder.add_node("plagiarism_check", plagiarism_wrapper)
    builder.add_node("figure_gen", figure_gen_wrapper)
    builder.add_node("figure_supervisor", figure_supervisor_wrapper)

    builder.set_entry_point("code_analyst")
    builder.add_edge("code_analyst", "writer")
    builder.add_edge("writer", "assessor")

    builder.add_conditional_edges("assessor", _should_rewrite, {
        "rewrite": "rewriter",
        "pass": "plagiarism_check",
    })
    builder.add_edge("rewriter", "assessor")

    builder.add_conditional_edges("plagiarism_check", _should_rewrite_plagiarism, {
        "rewrite": "rewriter",
        "pass": "figure_gen",
    })

    builder.add_edge("figure_gen", "figure_supervisor")
    builder.add_conditional_edges("figure_supervisor", _should_regenerate_figure, {
        "regenerate": "figure_gen",
        "pass": END,
    })

    return builder.compile()


def load_caches(state: dict) -> dict:
    """Load cached knowledge bases into state before the run."""
    updates = {}

    if is_cache_fresh(STYLE_CACHE_PATH, max_age_days=30):
        style = load_cache(STYLE_CACHE_PATH)
        if style:
            updates["style_guide"] = style

    if is_cache_fresh(TELLS_CACHE_PATH, max_age_days=7):
        tells_raw = load_cache(TELLS_CACHE_PATH)
        if tells_raw:
            try:
                updates["ai_tells"] = json.loads(tells_raw)
            except json.JSONDecodeError:
                pass

    return updates
