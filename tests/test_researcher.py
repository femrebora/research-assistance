"""Tests for researcher.py — unit tests for core functions."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add parent dir to path so we can import researcher
sys.path.insert(0, str(Path(__file__).parent.parent))

from researcher import (
    _extract_citekey,
    _extract_metadata,
    build_context,
    chunk_text,
    deduplicate_by_source,
)


# ── chunk_text ───────────────────────────────────────────────────────────────


def _make_chunks(text: str, size: int, overlap: int) -> list[str]:
    return [c for c in chunk_text(text, size=size, overlap=overlap) if c]


class TestChunkText:
    def test_basic_chunking(self):
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        chunks = _make_chunks(text, size=30, overlap=5)
        assert len(chunks) >= 2
        assert all(isinstance(c, str) for c in chunks)
        assert all(len(c) > 0 for c in chunks)

    def test_short_text_under_chunk_size(self):
        text = "Short text."
        chunks = _make_chunks(text, size=800, overlap=200)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_empty_text(self):
        chunks = _make_chunks("", size=800, overlap=200)
        assert len(chunks) == 0

    def test_whitespace_only(self):
        chunks = _make_chunks("   \n  \t  ", size=800, overlap=200)
        assert len(chunks) == 0

    def test_chunk_overlap_preserves_context(self):
        text = "A" * 100 + ". " + "B" * 100
        chunks = _make_chunks(text, size=80, overlap=40)
        assert len(chunks) > 1
        # Verify overlap: last chars of first chunk appear near start of second
        for i in range(len(chunks) - 1):
            end_of_first = chunks[i][-20:].strip(". ")
            start_of_second = chunks[i + 1][:80]
            # Some overlap should exist
            assert any(c in start_of_second for c in end_of_first if c.isalpha())

    def test_sentence_boundary_preference(self):
        text = "A" * 70 + ". " + "B" * 70 + ". " + "C" * 70 + "."
        chunks = _make_chunks(text, size=80, overlap=20)
        # Prefer breaking at ". " rather than mid-word
        for c in chunks[:-1]:
            c = c.rstrip()
            assert c.endswith(".") or len(c) <= 80

    def test_large_chunk_size(self):
        text = "Hello world. " * 50
        chunks = _make_chunks(text, size=2000, overlap=200)
        assert len(chunks) == 1


# ── _extract_citekey ─────────────────────────────────────────────────────────


class TestExtractCitekey:
    def test_from_extra_field(self):
        item = {"extra": "Citation Key: smith2024numt\nOther: value"}
        assert _extract_citekey(item) == "smith2024numt"

    def test_from_extra_field_whitespace(self):
        item = {"extra": "Citation Key:  jones2023  \nOther"}
        assert _extract_citekey(item) == "jones2023"

    def test_fallback_to_citekey_field(self):
        item = {"extra": "", "citekey": "lee2025"}
        assert _extract_citekey(item) == "lee2025"

    def test_no_citekey(self):
        item = {"extra": "Some notes"}
        assert _extract_citekey(item) is None

    def test_empty_item(self):
        assert _extract_citekey({}) is None


# ── _extract_metadata ────────────────────────────────────────────────────────


class TestExtractMetadata:
    def test_single_author(self):
        item = {
            "title": "Test Paper",
            "creators": [{"firstName": "John", "lastName": "Smith"}],
            "date": "2024-03-15",
            "DOI": "10.1234/test",
            "itemType": "journalArticle",
        }
        meta = _extract_metadata(item)
        assert meta["authors_short"] == "Smith"
        assert meta["title"] == "Test Paper"
        assert meta["year"] == "2024"
        assert meta["doi"] == "10.1234/test"

    def test_two_authors(self):
        item = {
            "creators": [
                {"lastName": "Smith"},
                {"lastName": "Jones"},
            ]
        }
        meta = _extract_metadata(item)
        assert meta["authors_short"] == "Smith & Jones"

    def test_three_plus_authors(self):
        item = {
            "creators": [
                {"lastName": "Smith"},
                {"lastName": "Jones"},
                {"lastName": "Lee"},
            ]
        }
        meta = _extract_metadata(item)
        assert meta["authors_short"] == "Smith et al."

    def test_no_authors(self):
        meta = _extract_metadata({"creators": []})
        assert meta["authors_short"] == ""

    def test_no_date(self):
        meta = _extract_metadata({"creators": []})
        assert meta["year"] == ""


# ── deduplicate_by_source ────────────────────────────────────────────────────


class TestDeduplicateBySource:
    def _make_result(self, key: str, similarity: float) -> dict:
        return {
            "text": f"Text from {key}",
            "metadata": {"zotero_key": key, "citekey": key, "title": key},
            "similarity": similarity,
        }

    def test_groups_by_source(self):
        results = [
            self._make_result("A", 0.9),
            self._make_result("A", 0.8),
            self._make_result("B", 0.7),
        ]
        deduped = deduplicate_by_source(results, max_per_source=3)
        keys = [r["metadata"]["zotero_key"] for r in deduped]
        assert keys == ["A", "A", "B"]  # sorted by similarity

    def test_limits_per_source(self):
        results = [
            self._make_result("A", 0.9),
            self._make_result("A", 0.8),
            self._make_result("A", 0.7),
            self._make_result("B", 0.6),
        ]
        deduped = deduplicate_by_source(results, max_per_source=2)
        keys = [r["metadata"]["zotero_key"] for r in deduped]
        assert keys == ["A", "A", "B"]

    def test_sorts_by_similarity_desc(self):
        results = [
            self._make_result("A", 0.5),
            self._make_result("B", 0.9),
            self._make_result("C", 0.7),
        ]
        deduped = deduplicate_by_source(results, max_per_source=3)
        sims = [r["similarity"] for r in deduped]
        assert sims == [0.9, 0.7, 0.5]

    def test_empty(self):
        assert deduplicate_by_source([]) == []

    def test_handles_missing_zotero_key(self):
        result = {
            "text": "Text",
            "metadata": {"citekey": "test"},
            "similarity": 0.8,
        }
        deduped = deduplicate_by_source([result])
        assert len(deduped) == 1


# ── build_context ────────────────────────────────────────────────────────────


class TestBuildContext:
    def _make_result(self, key: str, citekey: str, title: str, similarity: float = 0.9) -> dict:
        return {
            "text": f"Sample text from {citekey}.",
            "metadata": {
                "zotero_key": key,
                "citekey": citekey,
                "title": title,
                "authors_short": "Smith",
                "year": "2024",
            },
            "similarity": similarity,
        }

    def test_includes_sources_and_excerpts(self):
        results = [self._make_result("A1", "smith2024", "Test Paper")]
        ctx = build_context(results)
        assert "## Sources" in ctx
        assert "## Relevant Excerpts" in ctx
        assert "@smith2024" in ctx
        assert "Test Paper" in ctx
        assert "Sample text from smith2024" in ctx

    def test_numbers_sources(self):
        results = [
            self._make_result("A1", "smith2024", "Paper A"),
            self._make_result("B2", "jones2023", "Paper B"),
        ]
        ctx = build_context(results)
        assert "[1]" in ctx
        assert "[2]" in ctx

    def test_empty_results(self):
        ctx = build_context([])
        assert "No relevant sources found" in ctx

    def test_includes_similarity_scores(self):
        results = [self._make_result("A1", "smith2024", "Paper", 0.85)]
        ctx = build_context(results)
        assert "0.85" in ctx

    def test_handles_missing_citekey(self):
        result = {
            "text": "Text without citekey.",
            "metadata": {"zotero_key": "A1", "citekey": "", "title": "Paper"},
            "similarity": 0.8,
        }
        ctx = build_context([result])
        assert "source-1" in ctx  # fallback naming
