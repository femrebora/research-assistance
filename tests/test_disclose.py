"""Tests for disclose.py — aggregation and rendering (no network)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from disclose import LogRecord, aggregate, load_logs, render_markdown


def _write_logs(tmp_path: Path, day: str, lines: list[dict]) -> None:
    f = tmp_path / f"{day}.jsonl"
    with f.open("w", encoding="utf-8") as fh:
        for ln in lines:
            fh.write(json.dumps(ln) + "\n")


class TestLoadLogs:
    def test_reads_jsonl(self, tmp_path):
        _write_logs(tmp_path, "2026-05-20", [
            {"timestamp": "2026-05-20T10:00:00+00:00",
             "model_alias": "claude", "model_full": "anthropic/claude-opus-4-7",
             "prompt": "hi", "response": "hello",
             "input_tokens": 100, "output_tokens": 50},
            {"timestamp": "2026-05-20T11:00:00+00:00",
             "model_alias": "gemini", "model_full": "gemini/gemini-2.5-pro",
             "prompt": "q", "response": "a",
             "input_tokens": 200, "output_tokens": 80},
        ])
        records = load_logs(log_dir=tmp_path)
        assert len(records) == 2
        assert records[0].model_alias == "claude"
        assert records[1].input_tokens == 200

    def test_skips_invalid_json(self, tmp_path):
        f = tmp_path / "2026-05-21.jsonl"
        f.write_text("not-json\n{\"model_alias\": \"gpt\", \"timestamp\": \"x\"}\n", encoding="utf-8")
        records = load_logs(log_dir=tmp_path)
        assert len(records) == 1
        assert records[0].model_alias == "gpt"

    def test_no_logs_returns_empty(self, tmp_path):
        records = load_logs(log_dir=tmp_path / "nonexistent")
        assert records == []


class TestAggregate:
    def test_totals_and_per_model(self):
        records = [
            LogRecord("2026-05-20T10:00:00+00:00", "claude", "anthropic/claude-opus-4-7",
                      10, 20, 1000, 500, via="api"),
            LogRecord("2026-05-20T11:00:00+00:00", "claude", "anthropic/claude-opus-4-7",
                      10, 20, 500, 200, via="api"),
            LogRecord("2026-05-20T12:00:00+00:00", "gemini", "gemini/gemini-2.5-pro",
                      10, 20, 2000, 800, via="api"),
        ]
        stats = aggregate(records)
        assert stats["total"]["calls"] == 3
        assert stats["total"]["input_tokens"] == 3500
        assert stats["total"]["output_tokens"] == 1500
        assert stats["by_model"]["claude"]["calls"] == 2
        assert stats["by_model"]["gemini"]["calls"] == 1
        # Claude: (1500/1M)*15 + (700/1M)*75 = 0.0225 + 0.0525 = 0.075
        assert pytest.approx(stats["by_model"]["claude"]["cost"], rel=1e-3) == 0.075

    def test_empty(self):
        stats = aggregate([])
        assert stats["total"]["calls"] == 0
        assert stats["by_model"] == {}
        assert stats["first_call"] is None
        assert stats["by_route"] == {"api": 0, "cli": 0}

    def test_cli_calls_not_counted_in_cost(self):
        records = [
            LogRecord("2026-05-20T10:00:00+00:00", "claude", "anthropic/claude-opus-4-7",
                      10, 20, 1000, 500, via="api"),
            LogRecord("2026-05-20T11:00:00+00:00", "claude-cli", "claude -p",
                      10, 20, None, None, via="cli"),
            LogRecord("2026-05-20T12:00:00+00:00", "claude-cli", "claude -p",
                      10, 20, None, None, via="cli"),
        ]
        stats = aggregate(records)
        assert stats["by_route"] == {"api": 1, "cli": 2}
        # Only the API call contributes to cost.
        api_cost = stats["by_model"]["claude"]["cost"]
        cli_cost = stats["by_model"]["claude-cli"]["cost"]
        assert api_cost > 0
        assert cli_cost == 0.0
        assert stats["by_model"]["claude-cli"]["via"] == "cli"
        assert stats["by_model"]["claude-cli"]["calls"] == 2


class TestRenderMarkdown:
    def test_includes_venue_template(self):
        records = [LogRecord("2026-05-20T10:00:00+00:00", "claude", "anthropic/claude-opus-4-7",
                             10, 20, 100, 50)]
        stats = aggregate(records)
        md = render_markdown(stats, venue="elsevier")
        assert "Declaration of generative AI" in md
        assert "`claude`" in md
        assert "anthropic/claude-opus-4-7" in md

    def test_no_records(self):
        stats = aggregate([])
        md = render_markdown(stats, venue="thesis")
        assert "No AI model calls were recorded" in md

    def test_unknown_venue_falls_back(self):
        records = [LogRecord("t", "gpt", "openai/gpt-5", 10, 20, 100, 50, via="api")]
        stats = aggregate(records)
        md = render_markdown(stats, venue="nonexistent")
        assert "AI-assisted writing disclosure" in md  # generic header

    def test_cli_calls_rendered_without_cost(self):
        records = [
            LogRecord("2026-05-20T10:00:00+00:00", "claude-cli", "claude -p",
                      10, 20, None, None, via="cli"),
        ]
        stats = aggregate(records)
        md = render_markdown(stats, venue="generic")
        assert "`claude-cli`" in md
        assert "n/a (CLI subscription)" in md
        assert "1 via CLI subscription" in md
