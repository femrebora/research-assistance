"""Integration test — full pipeline with mocked ask_model."""
from __future__ import annotations

import sys
import os
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


MOCK_CODE_ANALYST_RESPONSE = {
    "text": "## Pipeline Overview\nThe pipeline processes data in three stages.",
    "model": "gemini/gemini-2.5-pro",
    "input_tokens": 500, "output_tokens": 300, "cost": 0.002,
}

MOCK_WRITER_RESPONSE = {
    "text": "# Abstract\n\nThis paper presents a novel approach.\n\n# Introduction\n\nTest.\n\n# Methods\n\nBayesian.\n\n# Results\n\n95% sensitivity.\n\n# Discussion\n\nOutperforms.",
    "model": "deepseek/deepseek-chat",
    "input_tokens": 800, "output_tokens": 1200, "cost": 0.003,
}

MOCK_ASSESSOR_RESPONSE = {
    "text": '{"abstract": {"score": 8, "ai_score": 2, "critique": "Clear.", "ai_phrases": []}, "introduction": {"score": 8, "ai_score": 1, "critique": "Good.", "ai_phrases": []}, "methods": {"score": 8, "ai_score": 2, "critique": "Fine.", "ai_phrases": []}, "results": {"score": 8, "ai_score": 1, "critique": "Good.", "ai_phrases": []}, "discussion": {"score": 8, "ai_score": 1, "critique": "Strong.", "ai_phrases": []}, "overall_notes": "Excellent."}',
    "model": "anthropic/claude-opus-4-7",
    "input_tokens": 400, "output_tokens": 200, "cost": 0.02,
}

MOCK_PLAGIARISM_RESPONSE = {
    "text": '{"originality_pct": 92, "ai_likelihood_pct": 14, "flagged_passages": [], "notes": "Reads naturally."}',
    "model": "deepseek/deepseek-chat",
    "input_tokens": 300, "output_tokens": 100, "cost": 0.001,
}

MOCK_FIGURE_GEN_RESPONSE = {
    "text": "### Figure 1: Pipeline\n```python\nimport matplotlib.pyplot as plt\nplt.style.use('dark_background')\nfig, ax = plt.subplots()\nax.bar([1,2,3], [10,20,15])\nplt.savefig('fig1.png', dpi=300, bbox_inches='tight')\n```",
    "model": "gemini/gemini-2.5-pro",
    "input_tokens": 200, "output_tokens": 100, "cost": 0.001,
}

MOCK_FIGURE_SUPERVISOR_RESPONSE = {
    "text": '{"figures": [{"index": 0, "verdict": "PASS", "notes": "Good."}], "overall": "PASS", "summary": "Ready."}',
    "model": "anthropic/claude-opus-4-7",
    "input_tokens": 100, "output_tokens": 50, "cost": 0.01,
}


class TestFullPipeline:
    @patch("agentic.bridge.ask_model")
    def test_end_to_end_with_mocks(self, mock_ask):
        """Run the full pipeline with all agent responses mocked."""
        import tempfile
        from agentic.state import make_initial_state
        from agentic.orchestrator import build_graph

        mock_ask.side_effect = [
            MOCK_CODE_ANALYST_RESPONSE,
            MOCK_WRITER_RESPONSE,
            MOCK_ASSESSOR_RESPONSE,
            MOCK_PLAGIARISM_RESPONSE,
            MOCK_FIGURE_GEN_RESPONSE,
            MOCK_FIGURE_SUPERVISOR_RESPONSE,
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            code_dir = os.path.join(tmpdir, "code")
            os.makedirs(code_dir)
            Path(code_dir, "main.py").write_text("def pipeline():\n    pass\n")

            state = make_initial_state(
                code_path=code_dir,
                user_summary="A bioinformatics pipeline for NUMT filtering.",
                output_dir=os.path.join(tmpdir, "output"),
                max_rewrites=5,
            )

            graph = build_graph()
            final_state = graph.invoke(state)

            assert final_state["draft"] is not None
            assert "Abstract" in final_state["draft"]
            assert final_state["assessment"] is not None
            assert final_state["assessment"]["abstract"]["score"] == 8
            assert final_state["originality_score"] is not None
            assert final_state["originality_score"]["originality_pct"] == 92
            assert len(final_state["figures"]) >= 1
            assert len(final_state["agent_calls"]) == 6
            assert final_state["text_rewrite_count"] == 0

    @patch("agentic.bridge.ask_model")
    def test_rewrite_loop_triggers_on_low_score(self, mock_ask):
        """When assessor gives a low score, the rewrite loop activates."""
        import tempfile
        from agentic.state import make_initial_state
        from agentic.orchestrator import build_graph

        low_assessment = {
            "text": '{"methods": {"score": 5, "ai_score": 2, "critique": "Too vague.", "ai_phrases": []}, "overall_notes": "Needs work."}',
            "model": "anthropic/claude-opus-4-7",
            "input_tokens": 100, "output_tokens": 50, "cost": 0.01,
        }

        rewrite_response = {
            "text": "# Methods\n\nRevised methods with more detail.",
            "model": "anthropic/claude-opus-4-7",
            "input_tokens": 200, "output_tokens": 100, "cost": 0.02,
        }

        pass_assessment = {
            "text": '{"methods": {"score": 8, "ai_score": 1, "critique": "Much better.", "ai_phrases": []}, "overall_notes": "Good."}',
            "model": "anthropic/claude-opus-4-7",
            "input_tokens": 100, "output_tokens": 50, "cost": 0.01,
        }

        mock_ask.side_effect = [
            MOCK_CODE_ANALYST_RESPONSE,
            MOCK_WRITER_RESPONSE,
            low_assessment,
            rewrite_response,
            pass_assessment,
            MOCK_PLAGIARISM_RESPONSE,
            MOCK_FIGURE_GEN_RESPONSE,
            MOCK_FIGURE_SUPERVISOR_RESPONSE,
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            code_dir = os.path.join(tmpdir, "code")
            os.makedirs(code_dir)
            Path(code_dir, "main.py").write_text("x=1")

            state = make_initial_state(
                code_path=code_dir,
                user_summary="A test project.",
                output_dir=os.path.join(tmpdir, "out"),
                max_rewrites=5,
            )

            graph = build_graph()
            final_state = graph.invoke(state)

            assert final_state["text_rewrite_count"] >= 1
            assert len(final_state["agent_calls"]) >= 6
