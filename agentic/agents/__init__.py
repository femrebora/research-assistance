"""Agent functions — each takes PaperState, returns a state delta dict."""
from agentic.agents.ai_artifact_detector import run_ai_artifact_detector
from agentic.agents.assessor import run_assessor
from agentic.agents.code_analyst import run_code_analyst
from agentic.agents.figure_gen import run_figure_gen
from agentic.agents.figure_supervisor import run_figure_supervisor
from agentic.agents.plagiarism_check import run_plagiarism_check
from agentic.agents.rewriter import run_rewriter
from agentic.agents.style_researcher import run_style_researcher
from agentic.agents.writer import run_writer

__all__ = [
    "run_ai_artifact_detector",
    "run_assessor",
    "run_code_analyst",
    "run_figure_gen",
    "run_figure_supervisor",
    "run_plagiarism_check",
    "run_rewriter",
    "run_style_researcher",
    "run_writer",
]
