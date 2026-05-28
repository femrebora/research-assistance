"""Tests for agent functions."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCodeAnalyst:
    @patch("agentic.agents.code_analyst.call_agent")
    def test_produces_technical_report(self, mock_call):
        mock_call.return_value = {
            "text": "## Pipeline Overview\nThe pipeline consists of three stages...",
            "model": "gemini/gemini-2.5-pro",
            "input_tokens": 500, "output_tokens": 300, "cost": 0.002,
        }
        from agentic.agents.code_analyst import run_code_analyst

        with tempfile.TemporaryDirectory() as d:
            Path(d, "main.py").write_text("import sys\nprint('hello')\n")
            Path(d, "utils.py").write_text("def add(a,b): return a+b\n")
            delta = run_code_analyst({
                "code_path": d,
                "user_summary": "A test pipeline.",
            })

        assert delta["technical_report"] is not None
        assert "Pipeline Overview" in delta["technical_report"]
        assert len(delta["agent_calls"]) == 1
        assert delta["agent_calls"][0]["agent"] == "code_analyst"

    @patch("agentic.agents.code_analyst.call_agent")
    def test_uses_gemini_model(self, mock_call):
        mock_call.return_value = {
            "text": "report", "model": "gemini/gemini-2.5-pro",
            "input_tokens": 10, "output_tokens": 5, "cost": 0.0,
        }
        from agentic.agents.code_analyst import run_code_analyst
        with tempfile.TemporaryDirectory() as d:
            Path(d, "main.py").write_text("x=1")
            run_code_analyst({"code_path": d, "user_summary": "test"})
        assert mock_call.call_args[1]["model"] == "gemini"


class TestWriter:
    @patch("agentic.agents.writer.call_agent")
    def test_produces_draft(self, mock_call):
        mock_call.return_value = {
            "text": "# Abstract\n\nThis paper presents...\n\n# Introduction\n\n...",
            "model": "deepseek/deepseek-chat",
            "input_tokens": 800, "output_tokens": 1200, "cost": 0.003,
        }
        from agentic.agents.writer import run_writer

        state = {
            "technical_report": "Pipeline: preprocess → align → call → filter.",
            "style_guide": "Use active voice.",
            "user_summary": "A NUMT filtering pipeline.",
            "rag_context": "",
            "agent_calls": [],
        }
        delta = run_writer(state)
        assert delta["draft"] is not None
        assert "Abstract" in delta["draft"]
        assert len(delta["agent_calls"]) == 1
        assert delta["agent_calls"][0]["agent"] == "writer"

    @patch("agentic.agents.writer.call_agent")
    def test_uses_deepseek_model(self, mock_call):
        mock_call.return_value = {
            "text": "draft", "model": "deepseek/deepseek-chat",
            "input_tokens": 1, "output_tokens": 1, "cost": 0,
        }
        from agentic.agents.writer import run_writer
        run_writer({"technical_report": "", "style_guide": "", "user_summary": "", "rag_context": "", "agent_calls": []})
        assert mock_call.call_args[1]["model"] == "deepseek"


class TestAssessor:
    @patch("agentic.agents.assessor.call_agent")
    def test_parses_valid_json(self, mock_call):
        mock_call.return_value = {
            "text": '{"abstract": {"score": 8, "ai_score": 2, "critique": "Good.", "ai_phrases": []}, "overall_notes": "Solid."}',
            "model": "anthropic/claude-opus-4-7",
            "input_tokens": 400, "output_tokens": 200, "cost": 0.02,
        }
        from agentic.agents.assessor import run_assessor

        state = {"draft": "# Abstract\n\nTest.", "ai_tells": None, "agent_calls": []}
        delta = run_assessor(state)
        assert delta["assessment"]["abstract"]["score"] == 8
        assert delta["assessment"]["overall_notes"] == "Solid."
        assert len(delta["agent_calls"]) == 1

    @patch("agentic.agents.assessor.call_agent")
    def test_handles_json_in_markdown_fence(self, mock_call):
        mock_call.return_value = {
            "text": '```json\n{"abstract": {"score": 7, "ai_score": 3, "critique": "Fine", "ai_phrases": ["delve"]}, "overall_notes": "ok"}\n```',
            "model": "anthropic/claude-opus-4-7",
            "input_tokens": 100, "output_tokens": 50, "cost": 0.01,
        }
        from agentic.agents.assessor import run_assessor
        state = {"draft": "test", "ai_tells": None, "agent_calls": []}
        delta = run_assessor(state)
        assert delta["assessment"]["abstract"]["score"] == 7

    @patch("agentic.agents.assessor.call_agent")
    def test_uses_claude_model(self, mock_call):
        mock_call.return_value = {
            "text": '{"overall_notes": "test"}',
            "model": "anthropic/claude-opus-4-7",
            "input_tokens": 1, "output_tokens": 1, "cost": 0,
        }
        from agentic.agents.assessor import run_assessor
        run_assessor({"draft": "", "ai_tells": {}, "agent_calls": []})
        assert mock_call.call_args[1]["model"] == "claude"


class TestRewriter:
    @patch("agentic.agents.rewriter.call_agent")
    def test_produces_revised_draft(self, mock_call):
        mock_call.return_value = {
            "text": "# Abstract\n\nRevised abstract text.",
            "model": "anthropic/claude-opus-4-7",
            "input_tokens": 300, "output_tokens": 400, "cost": 0.03,
        }
        from agentic.agents.rewriter import run_rewriter

        state = {
            "draft": "# Abstract\n\nOriginal text.",
            "assessment": {"methods": {"score": 5, "critique": "Too vague."}},
            "ai_tells": {"overused_words": ["delve"]},
            "text_rewrite_count": 1,
            "agent_calls": [],
        }
        delta = run_rewriter(state)
        assert delta["text_rewrite_count"] == 2
        assert "Revised" in delta["draft"]
        assert delta["agent_calls"][0]["agent"] == "rewriter"

    @patch("agentic.agents.rewriter.call_agent")
    def test_increments_rewrite_count(self, mock_call):
        mock_call.return_value = {"text": "fixed", "model": "x", "input_tokens": 1, "output_tokens": 1, "cost": 0}
        from agentic.agents.rewriter import run_rewriter
        delta = run_rewriter({
            "draft": "", "assessment": {}, "ai_tells": None,
            "text_rewrite_count": 3, "agent_calls": [],
        })
        assert delta["text_rewrite_count"] == 4

    @patch("agentic.agents.rewriter.call_agent")
    def test_uses_claude_model(self, mock_call):
        mock_call.return_value = {"text": "ok", "model": "x", "input_tokens": 1, "output_tokens": 1, "cost": 0}
        from agentic.agents.rewriter import run_rewriter
        run_rewriter({"draft": "", "assessment": {}, "ai_tells": None, "text_rewrite_count": 0, "agent_calls": []})
        assert mock_call.call_args[1]["model"] == "claude"


class TestPlagiarismCheck:
    @patch("agentic.agents.plagiarism_check.call_agent")
    def test_parses_valid_scores(self, mock_call):
        mock_call.return_value = {
            "text": '{"originality_pct": 92, "ai_likelihood_pct": 14, "flagged_passages": [], "notes": "Reads naturally."}',
            "model": "deepseek/deepseek-chat",
            "input_tokens": 300, "output_tokens": 100, "cost": 0.001,
        }
        from agentic.agents.plagiarism_check import run_plagiarism_check
        state = {"draft": "Some text.", "ai_tells": None, "agent_calls": []}
        delta = run_plagiarism_check(state)
        assert delta["originality_score"]["originality_pct"] == 92
        assert delta["originality_score"]["ai_likelihood_pct"] == 14
        assert len(delta["agent_calls"]) == 1

    @patch("agentic.agents.plagiarism_check.call_agent")
    def test_uses_deepseek_model(self, mock_call):
        mock_call.return_value = {
            "text": '{"originality_pct": 80, "ai_likelihood_pct": 20, "flagged_passages": [], "notes": ""}',
            "model": "deepseek/deepseek-chat",
            "input_tokens": 1, "output_tokens": 1, "cost": 0,
        }
        from agentic.agents.plagiarism_check import run_plagiarism_check
        run_plagiarism_check({"draft": "", "ai_tells": None, "agent_calls": []})
        assert mock_call.call_args[1]["model"] == "deepseek"


class TestFigureGen:
    @patch("agentic.agents.figure_gen.subprocess.run")
    @patch("agentic.agents.figure_gen.call_agent")
    def test_produces_figures_list(self, mock_call, mock_run):
        mock_call.return_value = {
            "text": "### Figure 1: Pipeline\n```python\nimport matplotlib.pyplot as plt\nplt.figure()\nplt.savefig('fig1.png')\n```",
            "model": "gemini/gemini-2.5-pro",
            "input_tokens": 200, "output_tokens": 100, "cost": 0.001,
        }

        from agentic.agents.figure_gen import run_figure_gen
        from pathlib import Path

        with tempfile.TemporaryDirectory() as d:
            # Mock subprocess.run to create the expected PNG file
            def _mock_run(*args, **kwargs):
                fig_path = Path(d) / "figures" / "figure_1.png"
                fig_path.parent.mkdir(parents=True, exist_ok=True)
                fig_path.write_text("dummy png content")
                return subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                )

            mock_run.side_effect = _mock_run

            state = {
                "technical_report": "Pipeline.",
                "code_path": d,
                "output_dir": d,
                "agent_calls": [],
            }
            delta = run_figure_gen(state)

        assert len(delta["figures"]) >= 1
        assert "code" in delta["figures"][0]
        assert delta["figures"][0]["png_path"] is not None
        assert "figure_1.png" in delta["figures"][0]["png_path"]
        assert delta["agent_calls"][0]["agent"] == "figure_gen"

    @patch("agentic.agents.figure_gen.subprocess.run")
    @patch("agentic.agents.figure_gen.call_agent")
    def test_executes_code_for_each_figure(self, mock_call, mock_run):
        mock_call.return_value = {
            "text": (
                "### Figure 1: Market\n```python\nimport matplotlib.pyplot as plt\nplt.savefig('m.png')\n```\n\n"
                "### Figure 2: Timeline\n```python\nimport matplotlib.pyplot as plt\nplt.savefig('t.png')\n```"
            ),
            "model": "gemini/gemini-2.5-pro",
            "input_tokens": 300, "output_tokens": 200, "cost": 0.002,
        }

        from agentic.agents.figure_gen import run_figure_gen
        from pathlib import Path

        call_count = 0

        def _mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            fig_path = Path(d) / "figures" / f"figure_{call_count}.png"
            fig_path.parent.mkdir(parents=True, exist_ok=True)
            fig_path.write_text("dummy")
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

        mock_run.side_effect = _mock_run

        with tempfile.TemporaryDirectory() as d:
            state = {
                "technical_report": "Review content.",
                "code_path": d,
                "output_dir": d,
                "agent_calls": [],
            }
            delta = run_figure_gen(state)

        assert len(delta["figures"]) == 2
        assert call_count == 2
        for fig in delta["figures"]:
            assert fig["png_path"] is not None

    @patch("agentic.agents.figure_gen.call_agent")
    def test_handles_missing_output_dir(self, mock_call):
        mock_call.return_value = {
            "text": "### Figure 1: Test\n```python\nprint('test')\n```",
            "model": "gemini/gemini-2.5-pro",
            "input_tokens": 50, "output_tokens": 25, "cost": 0.0,
        }
        from agentic.agents.figure_gen import run_figure_gen
        delta = run_figure_gen({"agent_calls": []})
        assert delta["figures"] == []
        assert delta["agent_calls"][0]["agent"] == "figure_gen"


class TestFigureSupervisor:
    @patch("agentic.agents.figure_supervisor.call_agent")
    def test_reviews_figures(self, mock_call):
        mock_call.return_value = {
            "text": '{"figures": [{"index": 0, "verdict": "PASS", "notes": "Good"}], "overall": "PASS", "summary": "All good."}',
            "model": "anthropic/claude-opus-4-7",
            "input_tokens": 100, "output_tokens": 50, "cost": 0.01,
        }
        from agentic.agents.figure_supervisor import run_figure_supervisor
        state = {
            "figures": [{"title": "Fig1", "code": "plt.plot()", "png_path": None, "review": None}],
            "figure_rewrite_count": 0, "agent_calls": [],
        }
        delta = run_figure_supervisor(state)
        assert delta["figure_rewrite_count"] == 1
        assert "review" in delta["figures"][0]
        assert delta["figures"][0]["review"]["verdict"] == "PASS"


class TestStyleResearcher:
    @patch("agentic.agents.style_researcher.call_agent")
    @patch("agentic.agents.style_researcher.save_cache")
    def test_produces_style_guide(self, mock_save, mock_call):
        mock_call.return_value = {
            "text": "# Bioinformatics Style Guide\n\nUse active voice.",
            "model": "deepseek/deepseek-chat",
            "input_tokens": 200, "output_tokens": 500, "cost": 0.002,
        }
        from agentic.agents.style_researcher import run_style_researcher
        delta = run_style_researcher({"domain": "bioinformatics", "agent_calls": []})
        assert "Use active voice" in delta["style_guide"]
        mock_save.assert_called_once()
        assert delta["agent_calls"][0]["agent"] == "style_researcher"


class TestAIArtifactDetector:
    @patch("agentic.agents.ai_artifact_detector.call_agent")
    @patch("agentic.agents.ai_artifact_detector.save_cache")
    def test_produces_ai_tells(self, mock_save, mock_call):
        mock_call.return_value = {
            "text": '{"overused_words": ["delve", "crucial"], "formulaic_structures": [], "hedging_overuse": [], "ai_sentence_patterns": [], "stylistic_uniformity_markers": []}',
            "model": "gemini/gemini-2.5-pro",
            "input_tokens": 200, "output_tokens": 300, "cost": 0.002,
        }
        from agentic.agents.ai_artifact_detector import run_ai_artifact_detector
        delta = run_ai_artifact_detector({"agent_calls": []})
        assert delta["ai_tells"]["overused_words"] == ["delve", "crucial"]
        assert "last_updated" in delta["ai_tells"]
        assert delta["agent_calls"][0]["agent"] == "ai_artifact_detector"
