"""Tests for paraphrase_check.py — paragraph splitter (LLM-free)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from paraphrase_check import split_paragraphs


class TestSplitParagraphs:
    def test_basic(self):
        text = "Paragraph one.\n\nParagraph two."
        assert split_paragraphs(text) == ["Paragraph one.", "Paragraph two."]

    def test_strips_heading_only_blocks(self):
        text = "# Chapter 1\n\nReal paragraph here.\n\n## Section 1"
        assert split_paragraphs(text) == ["Real paragraph here."]

    def test_strips_list_only_blocks(self):
        text = "- item one\n- item two\n\nA real paragraph follows."
        assert split_paragraphs(text) == ["A real paragraph follows."]

    def test_strips_blockquote_only(self):
        text = "> quoted line\n> another quote\n\nReal paragraph."
        assert split_paragraphs(text) == ["Real paragraph."]

    def test_empty(self):
        assert split_paragraphs("") == []
        assert split_paragraphs("\n\n\n") == []

    def test_collapses_multiple_blank_lines(self):
        text = "Para A.\n\n\n\nPara B."
        assert split_paragraphs(text) == ["Para A.", "Para B."]
