"""Tests for audit.py — pure functions."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from audit import (
    build_audit,
    find_duplicate_bib_keys,
    paragraph_keys,
    split_paragraphs,
    word_count,
)


class TestSplitParagraphs:
    def test_basic(self):
        text = "Para one.\n\nPara two.\n\nPara three."
        assert split_paragraphs(text) == ["Para one.", "Para two.", "Para three."]

    def test_single_paragraph(self):
        assert split_paragraphs("Just one paragraph.") == ["Just one paragraph."]

    def test_empty(self):
        assert split_paragraphs("") == []

    def test_keeps_trailing_punctuation(self):
        assert split_paragraphs("End.\n\nNext!") == ["End.", "Next!"]


class TestParagraphKeys:
    def test_single_bracket(self):
        assert paragraph_keys("Cited [@smith2024].") == ["smith2024"]

    def test_multiple_in_bracket(self):
        assert paragraph_keys("Cited [@a; @b; @c].") == ["a", "b", "c"]

    def test_bare_citation(self):
        assert paragraph_keys("As @smith2024 showed.") == ["smith2024"]

    def test_email_not_counted(self):
        assert paragraph_keys("Contact me@example.com please.") == []


class TestWordCount:
    def test_basic(self):
        assert word_count("one two three") == 3

    def test_strips_citation_blocks(self):
        assert word_count("Important claim [@smith2024] here.") == 3

    def test_handles_hyphen(self):
        assert word_count("state-of-the-art") == 1


class TestFindDuplicateBibKeys:
    def test_unique(self):
        bib = "@article{a, x={1}}\n@book{b, y={2}}"
        assert find_duplicate_bib_keys(bib) == []

    def test_duplicate(self):
        bib = "@article{a, x={1}}\n@book{a, y={2}}\n@misc{a, z={3}}"
        dups = find_duplicate_bib_keys(bib)
        assert dups == [("a", 3)]


class TestBuildAudit:
    def test_summary_numbers(self):
        draft = (
            "This is paragraph one with a citation [@a].\n\n"
            "Paragraph two also cites a [@a] and adds b [@b].\n\n"
            "Paragraph three cites c [@c] [@c] [@c] heavily and is long enough to be "
            "considered a real paragraph for the purpose of single-source flagging. "
            "It continues with several more words to clear the 80-word minimum that "
            "the audit function enforces, padding padding padding padding padding "
            "padding padding padding padding padding padding padding padding padding."
        )
        bib = "@article{a, t={A}}\n@book{b, t={B}}\n@book{c, t={C}}\n@misc{d, t={D}}"
        report = build_audit(draft, bib, over_cite=2)

        assert report["total_citations"] == 6
        assert report["per_source"]["c"] == 3
        assert report["per_source"]["a"] == 2
        assert ("c", 3) in report["over_cited"]
        assert "d" in report["unused_bib_entries"]
        assert report["missing_citations"] == []

    def test_missing_citation_detected(self):
        draft = "Some text with [@missing] citation."
        bib = "@article{a, t={A}}"
        report = build_audit(draft, bib, over_cite=5)
        assert report["missing_citations"] == ["missing"]

    def test_duplicate_bib_flagged(self):
        draft = "Cited [@a]."
        bib = "@article{a, t={X}}\n@book{a, t={Y}}"
        report = build_audit(draft, bib, over_cite=5)
        assert report["duplicate_bib_keys"] == [("a", 2)]
