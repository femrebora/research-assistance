"""Tests for the CLI-routing layer in common.py.

Validates that:
  - CLI aliases land in MODELS with a `cli:` prefixed value.
  - _ask_via_cli builds the right argv and surfaces a clean error when the
    binary is missing.
  - System prompts are inlined since CLIs lack a standard system-prompt slot.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from common import MODELS, _ask_via_cli, open_in_editor


class TestCliAliases:
    def test_aliases_registered(self):
        for alias in ("claude-cli", "gemini-cli", "codex-cli", "ollama-cli"):
            assert alias in MODELS, f"{alias} should be in MODELS"
            assert MODELS[alias].startswith("cli:"), f"{alias} value must be cli: prefixed"

    def test_api_aliases_still_present(self):
        # Sanity: adding CLI aliases must not displace existing API ones.
        for alias in ("claude", "gemini", "gpt", "deepseek", "sonnet", "haiku"):
            assert alias in MODELS
            assert not MODELS[alias].startswith("cli:")


class TestAskViaCli:
    def test_missing_binary_raises_runtime_error(self):
        with pytest.raises(RuntimeError, match="not found in PATH"):
            _ask_via_cli("hi", "claude-cli", "definitely-not-a-real-binary-xyz")

    def test_invokes_correct_argv(self):
        """The prompt must be appended as the final argv element (no shell)."""
        class _FakeProc:
            returncode = 0
            stdout = "model output here"
            stderr = ""

        with patch("common.subprocess.run", return_value=_FakeProc()) as run_mock:
            result = _ask_via_cli("THE PROMPT", "claude-cli", "claude -p")

        called_argv = run_mock.call_args.args[0]
        assert called_argv[0] == "claude"
        assert called_argv[1] == "-p"
        assert called_argv[-1] == "THE PROMPT"
        assert run_mock.call_args.kwargs["capture_output"] is True
        assert run_mock.call_args.kwargs["check"] is False
        assert result["text"] == "model output here"
        assert result["cost"] == 0.0
        assert result["input_tokens"] is None

    def test_system_prompt_is_inlined(self):
        """CLIs lack a system-role slot, so system text is prepended to the prompt."""
        class _FakeProc:
            returncode = 0
            stdout = "ok"
            stderr = ""

        with patch("common.subprocess.run", return_value=_FakeProc()) as run_mock:
            _ask_via_cli("user q", "gemini-cli", "gemini -p", system="be terse")

        final_prompt = run_mock.call_args.args[0][-1]
        assert "[System]" in final_prompt
        assert "be terse" in final_prompt
        assert "[User]" in final_prompt
        assert "user q" in final_prompt

    def test_nonzero_exit_raises(self):
        class _FakeProc:
            returncode = 2
            stdout = ""
            stderr = "auth error: missing token"

        with patch("common.subprocess.run", return_value=_FakeProc()):
            with pytest.raises(RuntimeError, match="exit 2"):
                _ask_via_cli("hi", "codex-cli", "codex exec")


class TestOpenInEditor:
    def test_returns_edited_content(self, tmp_path, monkeypatch):
        # Simulate an editor that appends a marker to the file it's handed.
        def fake_editor(argv):
            target = argv[-1]
            with open(target, "a", encoding="utf-8") as f:
                f.write("\nEDITED")
            return 0

        monkeypatch.setattr("common.subprocess.call", fake_editor)
        monkeypatch.setenv("EDITOR", "/usr/bin/true")

        result = open_in_editor("original text", suffix=".test")
        assert result.startswith("original text")
        assert result.endswith("EDITED")
