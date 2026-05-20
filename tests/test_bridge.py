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
    @patch("agentic.bridge.ask_model")
    def test_call_agent_returns_text(self, mock_ask):
        mock_ask.return_value = {
            "text": "Hello from model",
            "model": "test/model",
            "input_tokens": 10,
            "output_tokens": 5,
            "cost": 0.001,
        }
        result = call_agent(
            prompt="Say hello",
            model="gemini",
            system="You are helpful.",
            temperature=0.3,
        )
        assert result["text"] == "Hello from model"
        assert result["model"] == "test/model"
        mock_ask.assert_called_once_with(
            prompt="Say hello",
            model="gemini",
            system="You are helpful.",
            temperature=0.3,
        )

    @patch("agentic.bridge.ask_model")
    def test_call_agent_defaults(self, mock_ask):
        mock_ask.return_value = {"text": "ok", "model": "x", "input_tokens": 1, "output_tokens": 1, "cost": 0}
        call_agent(prompt="test")
        mock_ask.assert_called_once_with(
            prompt="test",
            model="claude",
            system=None,
            temperature=0.3,
        )


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
