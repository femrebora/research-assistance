"""Integration test — full pipeline with mocked LLM backends."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))


def _make_result(stdout_text):
    """Helper to create a mock subprocess.CompletedProcess."""
    r = MagicMock()
    r.stdout = stdout_text
    r.stderr = ""
    r.returncode = 0
    return r


def _make_deepseek_response(text):
    """Helper to create a mock urllib response for DeepSeek API."""
    body = json.dumps({
        "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }).encode("utf-8")
    r = MagicMock()
    r.read.return_value = body
    r.__enter__ = MagicMock(return_value=r)
    r.__exit__ = MagicMock(return_value=None)
    return r


MOCK_CODE_ANALYST = "## Pipeline Overview\nThe pipeline processes data in three stages."

MOCK_WRITER = "# Abstract\n\nThis paper presents a novel approach.\n\n# Introduction\n\nTest.\n\n# Methods\n\nBayesian.\n\n# Results\n\n95% sensitivity.\n\n# Discussion\n\nOutperforms."

# Valid JSON: note comma between key-value pairs
MOCK_ASSESSOR = (
    '{"abstract": {"score": 8, "ai_score": 2, "critique": "Clear.", "ai_phrases": []},'
    ' "introduction": {"score": 8, "ai_score": 1, "critique": "Good.", "ai_phrases": []},'
    ' "methods": {"score": 8, "ai_score": 2, "critique": "Fine.", "ai_phrases": []},'
    ' "results": {"score": 8, "ai_score": 1, "critique": "Good.", "ai_phrases": []},'
    ' "discussion": {"score": 8, "ai_score": 1, "critique": "Strong.", "ai_phrases": []},'
    ' "overall_notes": "Excellent."}'
)

MOCK_PLAGIARISM = (
    '{"originality_pct": 92, "ai_likelihood_pct": 14,'
    ' "flagged_passages": [], "notes": "Reads naturally."}'
)

MOCK_FIGURE_GEN = (
    "### Figure 1: Pipeline\n```python\nimport matplotlib.pyplot as plt\n"
    "plt.style.use('dark_background')\nfig, ax = plt.subplots()\n"
    "ax.bar([1,2,3], [10,20,15])\nplt.savefig('fig1.png', dpi=300, bbox_inches='tight')\n```"
)

MOCK_FIGURE_SUPERVISOR = (
    '{"figures": [{"index": 0, "verdict": "PASS", "notes": "Good."}],'
    ' "overall": "PASS", "summary": "Ready."}'
)


class TestFullPipeline:
    @patch("agentic.bridge.DEEPSEEK_API_KEY", "test-deepseek-key")
    @patch("agentic.bridge.urllib.request.urlopen")
    @patch("agentic.bridge.subprocess.run")
    def test_end_to_end_with_mocks(self, mock_run, mock_urlopen):
        """Run the full pipeline with all agent responses mocked.

        Mocks both subprocess.run (Claude/Gemini CLI) and urllib (DeepSeek API).
        All section scores are 8, so no rewrite should trigger.
        """
        import tempfile

        from agentic.orchestrator import build_graph
        from agentic.state import make_initial_state

        # DeepSeek returns valid content via API mock
        deepseek_writer = _make_deepseek_response(MOCK_WRITER)
        deepseek_plagiarism = _make_deepseek_response(MOCK_PLAGIARISM)

        # DeepSeek is called for Writer and Plagiarism (2 API calls)
        mock_urlopen.side_effect = [deepseek_writer, deepseek_plagiarism]

        # CLI calls: Code Analyst, Assessor, Figure Gen, Figure Supervisor
        mock_run.side_effect = [
            _make_result(MOCK_CODE_ANALYST),     # Code Analyst (gemini)
            _make_result(MOCK_ASSESSOR),          # Assessor (claude)
            _make_result(MOCK_FIGURE_GEN),        # Figure Gen (gemini)
            _make_result(MOCK_FIGURE_SUPERVISOR), # Figure Supervisor (claude)
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

    @patch("agentic.bridge.DEEPSEEK_API_KEY", "test-deepseek-key")
    @patch("agentic.bridge.urllib.request.urlopen")
    @patch("agentic.bridge.subprocess.run")
    def test_rewrite_loop_triggers_on_low_score(self, mock_run, mock_urlopen):
        """When assessor gives a low score, the rewrite loop activates."""
        import tempfile

        from agentic.orchestrator import build_graph
        from agentic.state import make_initial_state

        low_assessment = (
            '{"methods": {"score": 5, "ai_score": 2,'
            ' "critique": "Too vague.", "ai_phrases": []},'
            ' "overall_notes": "Needs work."}'
        )
        rewrite_response = "# Methods\n\nRevised methods with more detail."
        pass_assessment = (
            '{"methods": {"score": 8, "ai_score": 1,'
            ' "critique": "Much better.", "ai_phrases": []},'
            ' "overall_notes": "Good."}'
        )

        # DeepSeek API: Writer (uses MOCK_WRITER from first test var), Plagiarism
        deepseek_writer = _make_deepseek_response(MOCK_WRITER)
        deepseek_plagiarism = _make_deepseek_response(MOCK_PLAGIARISM)
        mock_urlopen.side_effect = [deepseek_writer, deepseek_plagiarism]

        # Pipeline: Code Analyst → Writer(deepseek) → Assessor(low,5) → Rewriter →
        # Assessor(pass,8) → Plagiarism → Figure Gen → Figure Supervisor
        mock_run.side_effect = [
            _make_result(MOCK_CODE_ANALYST),     # Code Analyst (gemini)
            _make_result(low_assessment),          # Assessor (claude, triggers rewrite)
            _make_result(rewrite_response),        # Rewriter (claude)
            _make_result(pass_assessment),         # Assessor (claude, passes)
            _make_result(MOCK_FIGURE_GEN),         # Figure Gen (gemini)
            _make_result(MOCK_FIGURE_SUPERVISOR),  # Figure Supervisor (claude)
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            code_dir = os.path.join(tmpdir, "code")
            os.makedirs(code_dir)
            Path(code_dir, "main.py").write_text("x=1")

            state = make_initial_state(
                code_path=code_dir,
                user_summary="A test project.",
                output_dir=os.path.join(tmpdir, "out"),
                max_rewrites=3,
            )

            graph = build_graph()
            final_state = graph.invoke(state)

            assert final_state["text_rewrite_count"] >= 1
            assert len(final_state["agent_calls"]) >= 6
