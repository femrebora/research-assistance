"""Tests for coherence.py — paragraph splitter and prompt block builder."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from coherence import build_paragraph_block, split_paragraphs


class TestSplitParagraphs:
    def test_strips_heading_blocks(self):
        text = "# Heading\n\nReal paragraph."
        assert split_paragraphs(text) == ["Real paragraph."]

    def test_keeps_real_paragraphs(self):
        text = "First.\n\nSecond.\n\nThird."
        assert split_paragraphs(text) == ["First.", "Second.", "Third."]

    def test_empty(self):
        assert split_paragraphs("") == []


class TestBuildParagraphBlock:
    def test_numbers_paragraphs(self):
        out = build_paragraph_block(["First.", "Second."])
        assert "Paragraph 1" in out
        assert "Paragraph 2" in out
        assert "First." in out
        assert "Second." in out

    def test_truncates_long_paragraphs(self):
        long_para = "x" * 1000
        out = build_paragraph_block([long_para], max_chars=100)
        assert "[...truncated]" in out
        assert "x" * 1000 not in out

    def test_short_paragraph_not_truncated(self):
        out = build_paragraph_block(["short"], max_chars=100)
        assert "[...truncated]" not in out
