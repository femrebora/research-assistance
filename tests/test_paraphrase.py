"""Tests for paraphrase.py — pure helpers (no network)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from paraphrase import StageResult, format_chain


def _stage(label: str, text: str, in_tokens=10, out_tokens=20, cost=0.001):
    return StageResult(
        label=label,
        model=f"test/{label}",
        text=text,
        input_tokens=in_tokens,
        output_tokens=out_tokens,
        cost=cost,
    )


class TestFormatChain:
    def test_includes_all_stages(self):
        stages = [
            _stage("writer", "Draft paragraph here."),
            _stage("paraphraser", "Paraphrased here."),
            _stage("checker", "VERDICT: SAFE"),
        ]
        md = format_chain("Test brief", stages)
        assert "## Brief" in md
        assert "Test brief" in md
        assert "Writer" in md
        assert "Draft paragraph here." in md
        assert "Paraphraser" in md
        assert "Paraphrased here." in md
        assert "Checker" in md
        assert "VERDICT: SAFE" in md

    def test_totals_in_footer(self):
        stages = [_stage("writer", "x", 100, 200, 0.005),
                  _stage("paraphraser", "y", 150, 100, 0.003)]
        md = format_chain("brief", stages)
        assert "250 in" in md
        assert "300 out" in md
        assert "$0.0080" in md

    def test_empty_stages_safe(self):
        md = format_chain("brief", [])
        assert "## Brief" in md
        assert "0 in" in md
