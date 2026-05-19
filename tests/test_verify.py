"""Tests for verify.py — citation extraction regex."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from verify import extract_bib_keys, extract_draft_keys


class TestExtractDraftKeys:
    def test_bare_citation(self):
        assert extract_draft_keys("See @smith2024 for details.") == ["smith2024"]

    def test_bracketed_citation(self):
        assert extract_draft_keys("Cited [@smith2024].") == ["smith2024"]

    def test_suppressed_author(self):
        assert extract_draft_keys("The result [-@smith2024] shows...") == ["smith2024"]

    def test_multiple_in_brackets(self):
        keys = extract_draft_keys("Several agree [@smith2024; @jones2023; @lee2025].")
        assert keys == ["smith2024", "jones2023", "lee2025"]

    def test_at_start_of_line(self):
        assert extract_draft_keys("@smith2024 argued this.") == ["smith2024"]

    def test_after_punctuation(self):
        assert extract_draft_keys("(@smith2024)") == ["smith2024"]

    def test_no_false_positive_on_email(self):
        # `me@example.com` should NOT be parsed as a citation to `example`.
        assert extract_draft_keys("Contact me@example.com for data.") == []

    def test_no_false_positive_on_path(self):
        # `/etc/passwd@foo` and `path/@bar` should not match.
        assert extract_draft_keys("File at /etc/passwd@v2 and path/@bar.") == []

    def test_no_false_positive_on_word_adjacent(self):
        assert extract_draft_keys("user@host and v1.2@release") == []

    def test_mixed_content(self):
        text = (
            "Contact ada@lovelace.org. As @smith2024 noted, [@jones2023] confirms. "
            "Other work [-@lee2025; @kim2022] adds context."
        )
        assert extract_draft_keys(text) == [
            "smith2024",
            "jones2023",
            "lee2025",
            "kim2022",
        ]


class TestExtractBibKeys:
    def test_article_entry(self):
        bib = "@article{smith2024, title={X}, year={2024}}"
        assert extract_bib_keys(bib) == {"smith2024"}

    def test_multiple_entries(self):
        bib = """
@article{smith2024, title={X}}
@book{jones2023, title={Y}}
@incollection{lee2025, title={Z}}
"""
        assert extract_bib_keys(bib) == {"smith2024", "jones2023", "lee2025"}

    def test_empty(self):
        assert extract_bib_keys("") == set()
