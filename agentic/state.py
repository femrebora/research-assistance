"""PaperState schema and initial state factory."""
from __future__ import annotations

from typing import TypedDict


class PaperState(TypedDict):
    """State carried through the LangGraph paper generation pipeline."""
    code_path: str
    user_summary: str
    output_dir: str
    style_guide: str | None
    ai_tells: dict | None
    technical_report: str | None
    benchmark_data: str | None
    draft: str | None
    assessment: dict | None
    originality_score: dict | None
    figures: list[dict] | None
    text_rewrite_count: int
    figure_rewrite_count: int
    max_rewrites: int
    agent_calls: list[dict]


def make_initial_state(
    code_path: str,
    user_summary: str,
    output_dir: str,
    *,
    max_rewrites: int = 5,
) -> PaperState:
    """Create the initial state for a paper generation run."""
    return PaperState(
        code_path=code_path,
        user_summary=user_summary,
        output_dir=output_dir,
        style_guide=None,
        ai_tells=None,
        technical_report=None,
        benchmark_data=None,
        draft=None,
        assessment=None,
        originality_score=None,
        figures=None,
        text_rewrite_count=0,
        figure_rewrite_count=0,
        max_rewrites=max_rewrites,
        agent_calls=[],
    )
