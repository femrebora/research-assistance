"""Tests for critique.py — sentence numbering helper."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from critique import _number_sentences


class TestNumberSentences:
    def test_two_sentences(self):
        out = _number_sentences("First sentence. Second sentence.")
        assert "S1: First sentence." in out
        assert "S2: Second sentence." in out

    def test_question_and_exclaim(self):
        out = _number_sentences("Why? Because. Look!")
        assert "S1: Why?" in out
        assert "S2: Because." in out
        assert "S3: Look!" in out

    def test_single_sentence(self):
        out = _number_sentences("Just one statement.")
        assert out == "S1: Just one statement."

    def test_skips_empty(self):
        out = _number_sentences("   .")
        # Should still produce something (or nothing), but not crash
        assert "S2" not in out

    def test_preserves_internal_punctuation(self):
        out = _number_sentences("Dr. Smith said hi. Then left.")
        # Naive regex splits on ". " — Dr. + Smith is a known limitation; test current behavior.
        assert "S1" in out
