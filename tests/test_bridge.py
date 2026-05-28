"""Tests for bridge layer — model calls and cache management."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from agentic.bridge import call_agent, load_cache, save_cache


class TestCallAgent:
    @patch("agentic.bridge.subprocess.run")
    def test_call_agent_returns_text_claude(self, mock_run):
        mock_run.return_value = type("R", (), {"stdout": "Hello from Claude", "stderr": ""})()
        result = call_agent(
            prompt="Say hello",
            model="claude",
            system="You are helpful.",
        )
        assert result["text"] == "Hello from Claude"
        assert result["model"] == "claude"

    @patch("agentic.bridge.subprocess.run")
    def test_call_agent_cli_route_gemini(self, mock_run):
        mock_run.return_value = type("R", (), {"stdout": "Hello from Gemini", "stderr": ""})()
        result = call_agent(prompt="Say hello", model="gemini")
        assert result["model"] == "gemini"

    @patch("agentic.bridge.subprocess.run")
    def test_call_agent_cli_route_deepseek(self, mock_run):
        mock_run.return_value = type("R", (), {"stdout": "Hello from DeepSeek", "stderr": ""})()
        result = call_agent(prompt="Say hello", model="deepseek")
        assert result["model"].startswith("deepseek")

    @patch("agentic.bridge.subprocess.run")
    def test_call_agent_includes_system_prompt(self, mock_run):
        mock_run.return_value = type("R", (), {"stdout": "OK", "stderr": ""})()
        call_agent(prompt="What is 2+2?", model="claude", system="Be concise.")
        # The command is now a list (shell=False)
        cmd_list = mock_run.call_args[0][0] if mock_run.call_args[0] else []
        cmd_string = " ".join(cmd_list)
        assert "Be concise" in cmd_string

    def test_call_agent_unknown_model_raises(self):
        import pytest
        with pytest.raises(ValueError, match="Unknown model"):
            call_agent(prompt="test", model="nonexistent")


class TestCacheOperations:
    def test_save_and_load_cache_md(self):
        with tempfile.TemporaryDirectory() as d:
            cache_path = str(Path(d) / "style_guide.md")
            save_cache(cache_path, "# Style Guide\n\nContent here.")
            loaded = load_cache(cache_path)
            assert loaded == "# Style Guide\n\nContent here."

    def test_save_and_load_cache_json(self):
        with tempfile.TemporaryDirectory() as d:
            cache_path = str(Path(d) / "ai_tells.json")
            data = {"overused_words": ["delve", "crucial"], "last_updated": "2026-05-20"}
            save_cache(cache_path, json.dumps(data))
            loaded = load_cache(cache_path)
            parsed = json.loads(loaded)
            assert parsed["overused_words"] == ["delve", "crucial"]

    def test_load_cache_missing_returns_none(self):
        result = load_cache("/tmp/nonexistent/cache/file.md")
        assert result is None

    def test_cache_age_days(self):
        from agentic.bridge import cache_age_days
        import time
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "test.md")
            Path(path).write_text("hello")
            age = cache_age_days(path)
            assert age is not None and age < 1.0

    def test_is_cache_fresh(self):
        from agentic.bridge import is_cache_fresh
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "test.md")
            Path(path).write_text("hello")
            assert is_cache_fresh(path, max_age_days=7) is True

    def test_is_cache_fresh_missing(self):
        from agentic.bridge import is_cache_fresh
        assert is_cache_fresh("/tmp/nonexistent_abc_123.md", max_age_days=7) is False
