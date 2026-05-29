"""Tests for PaperState schema and defaults."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agentic.state import PaperState, make_initial_state


class TestPaperState:
    def test_make_initial_state_sets_required_fields(self):
        state = make_initial_state(
            code_path="/home/user/project",
            user_summary="A bioinformatics pipeline for NUMT filtering.",
            output_dir="/home/user/thesis/output",
        )
        assert state["code_path"] == "/home/user/project"
        assert state["user_summary"] == "A bioinformatics pipeline for NUMT filtering."
        assert state["output_dir"] == "/home/user/thesis/output"

    def test_make_initial_state_sets_defaults(self):
        state = make_initial_state(
            code_path="/tmp/test",
            user_summary="Test project.",
            output_dir="/tmp/out",
        )
        assert state["technical_report"] is None
        assert state["draft"] is None
        assert state["assessment"] is None
        assert state["originality_score"] is None
        assert state["figures"] is None
        assert state["style_guide"] is None
        assert state["ai_tells"] is None
        assert state["text_rewrite_count"] == 0
        assert state["figure_rewrite_count"] == 0
        assert state["max_rewrites"] == 5
        assert state["agent_calls"] == []

    def test_make_initial_state_custom_max_rewrites(self):
        state = make_initial_state(
            code_path="/x", user_summary="y", output_dir="/z",
            max_rewrites=3,
        )
        assert state["max_rewrites"] == 3

    def test_paperstate_keys_match_spec(self):
        state = make_initial_state(code_path="/a", user_summary="b", output_dir="/c")
        required_keys = {
            "code_path", "user_summary", "output_dir",
            "research_topic", "research_data",
            "style_guide", "ai_tells", "technical_report",
            "benchmark_data", "draft", "assessment", "originality_score",
            "figures", "text_rewrite_count", "figure_rewrite_count",
            "max_rewrites", "agent_calls",
        }
        assert set(state.keys()) == required_keys
