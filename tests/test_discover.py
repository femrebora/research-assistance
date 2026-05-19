"""Tests for discover.py — pure helpers and data shapes."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from discover import Paper, _abstract_from_inverted, to_bibtex


class TestPaper:
    def test_first_author_last(self):
        p = Paper(title="X", authors=("Ada Lovelace", "Alan Turing"), year=2024)
        assert p.first_author_last == "Lovelace"

    def test_first_author_last_empty(self):
        p = Paper(title="X", authors=(), year=2024)
        assert p.first_author_last == ""

    def test_suggested_citekey(self):
        p = Paper(
            title="Numerical Mitochondrial Pseudogenes and Clinical Filtering",
            authors=("Alice Smith",),
            year=2024,
        )
        # last name lowercased + year + first content title word ≥ 4 chars
        assert p.suggested_citekey == "smith2024numerical"

    def test_suggested_citekey_skips_stopwords(self):
        p = Paper(
            title="The And With Filter For Mitochondria",
            authors=("Bob Jones",),
            year=2023,
        )
        # "The", "And", "With" excluded as stopwords; "For" too short; "Filter" first qualifies
        assert p.suggested_citekey == "jones2023filter"

    def test_suggested_citekey_no_year(self):
        p = Paper(title="Some Result", authors=("Lee Park",), year=None)
        # "Some" is 4 chars and not a stopword → first content word
        assert p.suggested_citekey == "parkndsome"

    def test_suggested_citekey_no_author(self):
        p = Paper(title="Untitled Work", authors=(), year=2024)
        assert p.suggested_citekey == "unknown2024"

    def test_immutable(self):
        p = Paper(title="X", authors=("A",), year=2024)
        with pytest.raises(Exception):
            p.title = "Y"  # type: ignore[misc]


class TestAbstractFromInverted:
    def test_reconstructs_order(self):
        inv = {"Hello": [0], "world": [1, 3], "cruel": [2]}
        assert _abstract_from_inverted(inv) == "Hello world cruel world"

    def test_empty(self):
        assert _abstract_from_inverted({}) == ""
        assert _abstract_from_inverted(None) == ""


class TestToBibtex:
    def test_minimal(self):
        p = Paper(title="A Paper", authors=("Ada Lovelace",), year=2024)
        out = to_bibtex(p)
        assert out.startswith("@article{lovelace2024paper,")
        assert "title = {A Paper}" in out
        assert "year = {2024}" in out
        assert "author = {Ada Lovelace}" in out

    def test_escapes_curly_braces_in_abstract(self):
        p = Paper(
            title="X",
            authors=("A B",),
            year=2024,
            abstract="Contains {curly} {braces}",
        )
        out = to_bibtex(p)
        # Braces inside abstract should be neutralized to avoid breaking BibTeX
        assert "{curly}" not in out
        assert "(curly)" in out
