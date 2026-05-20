"""Tests for the LangGraph orchestrator."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentic.orchestrator import _should_rewrite, _should_rewrite_plagiarism, _should_regenerate_figure, load_caches


class TestShouldRewrite:
    def test_pass_when_all_above_threshold(self):
        state = {
            "assessment": {
                "abstract": {"score": 8, "ai_score": 2},
                "methods": {"score": 9, "ai_score": 1},
            },
            "text_rewrite_count": 0,
            "max_rewrites": 5,
        }
        assert _should_rewrite(state) == "pass"

    def test_rewrite_when_one_below(self):
        state = {
            "assessment": {
                "abstract": {"score": 8, "ai_score": 2},
                "methods": {"score": 5, "ai_score": 1},
            },
            "text_rewrite_count": 0,
            "max_rewrites": 5,
        }
        assert _should_rewrite(state) == "rewrite"

    def test_pass_when_max_rewrites_reached(self):
        state = {
            "assessment": {"methods": {"score": 5}},
            "text_rewrite_count": 5,
            "max_rewrites": 5,
        }
        assert _should_rewrite(state) == "pass"

    def test_handles_empty_assessment(self):
        state = {"assessment": {}, "text_rewrite_count": 0, "max_rewrites": 5}
        assert _should_rewrite(state) == "pass"


class TestShouldRewritePlagiarism:
    def test_pass_high_originality(self):
        state = {
            "originality_score": {"originality_pct": 92, "ai_likelihood_pct": 14},
            "text_rewrite_count": 0,
            "max_rewrites": 5,
        }
        assert _should_rewrite_plagiarism(state) == "pass"

    def test_rewrite_low_originality(self):
        state = {
            "originality_score": {"originality_pct": 65, "ai_likelihood_pct": 10},
            "text_rewrite_count": 0,
            "max_rewrites": 5,
        }
        assert _should_rewrite_plagiarism(state) == "rewrite"

    def test_rewrite_high_ai_likelihood(self):
        state = {
            "originality_score": {"originality_pct": 85, "ai_likelihood_pct": 45},
            "text_rewrite_count": 0,
            "max_rewrites": 5,
        }
        assert _should_rewrite_plagiarism(state) == "rewrite"


class TestShouldRegenerateFigure:
    def test_pass_all_figures_ok(self):
        state = {
            "figures": [
                {"review": {"verdict": "PASS"}},
                {"review": {"verdict": "PASS"}},
            ],
            "figure_rewrite_count": 0,
            "max_rewrites": 5,
        }
        assert _should_regenerate_figure(state) == "pass"

    def test_regenerate_if_one_fails(self):
        state = {
            "figures": [
                {"review": {"verdict": "PASS"}},
                {"review": {"verdict": "FAIL", "notes": "Use viridis."}},
            ],
            "figure_rewrite_count": 0,
            "max_rewrites": 5,
        }
        assert _should_regenerate_figure(state) == "regenerate"


class TestLoadCaches:
    def test_load_caches_returns_dict(self):
        updates = load_caches({"agent_calls": []})
        assert isinstance(updates, dict)
