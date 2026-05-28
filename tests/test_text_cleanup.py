"""Tests for agentic/text_cleanup.py — mechanical prose post-processing."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agentic.text_cleanup import (
    cleanup_prose,
    remove_em_dashes,
    replace_en_dashes,
    split_long_sentences,
)


class TestRemoveEmDashes:
    def test_removes_em_dash_char(self):
        text = "The pipeline—if configured—runs quickly."
        result = remove_em_dashes(text)
        assert "—" not in result
        assert "pipeline" in result
        assert "runs quickly" in result

    def test_removes_triple_dash(self):
        text = "The approach---while complex---yields good results."
        result = remove_em_dashes(text)
        assert "---" not in result

    def test_no_dashes_unchanged(self):
        text = "The pipeline runs without any dashes."
        result = remove_em_dashes(text)
        assert result == text


class TestReplaceEnDashes:
    def test_numeric_range(self):
        text = "The method runs in 5–10 seconds."
        result = replace_en_dashes(text)
        assert "5 to 10" in result
        assert "–" not in result

    def test_multiple_ranges(self):
        text = "Parameters: 3–7 threads, 10–20 iterations."
        result = replace_en_dashes(text)
        assert "3 to 7" in result
        assert "10 to 20" in result

    def test_no_ranges_unchanged(self):
        text = "No numeric ranges here."
        result = replace_en_dashes(text)
        assert result == text


class TestSplitLongSentences:
    def test_short_sentences_unchanged(self):
        text = "First sentence. Second sentence. Third one here."
        result = split_long_sentences(text, max_words=35)
        assert result == text

    def test_preserves_markdown_headings(self):
        text = "# Abstract\n\nThis is a short abstract.\n\n# Methods\n\nThe methods are described here."
        result = split_long_sentences(text, max_words=35)
        assert "# Abstract" in result
        assert "# Methods" in result
        assert "Abstract" in result
        assert "Methods" in result

    def test_preserves_paragraph_breaks(self):
        text = "Paragraph one with content.\n\nParagraph two with more content."
        result = split_long_sentences(text, max_words=35)
        assert "\n\n" in result

    def test_preserves_code_blocks(self):
        text = "```python\nimport os\nx = 1\n```\n\nNormal text here."
        result = split_long_sentences(text, max_words=35)
        assert "```python" in result
        assert "import os" in result

    def test_splits_at_conjunction(self):
        text = "The pipeline processes trajectory data in three distinct computational stages which together form a cohesive analysis workflow for protein dynamics and functional annotation."
        result = split_long_sentences(text, max_words=10)
        parts = [s.strip() for s in result.split(".") if s.strip()]
        assert len(parts) >= 2

    def test_preserves_citations(self):
        text = "As shown previously [@smith2024] the method works well."
        result = split_long_sentences(text, max_words=35)
        assert "[@smith2024]" in result


class TestCleanupProse:
    def test_removes_em_dashes(self):
        text = "The method—while complex—is effective."
        result = cleanup_prose(text)
        assert "—" not in result

    def test_replaces_en_dashes(self):
        text = "Runtime of 5–10 seconds."
        result = cleanup_prose(text)
        assert "5 to 10" in result

    def test_preserves_markdown_structure(self):
        text = "# Title\n\nAbstract text.\n\n## Section\n\nBody text.\n\n| Col1 | Col2 |\n|------|------|\n| A | B |"
        result = cleanup_prose(text)
        assert "# Title" in result
        assert "## Section" in result
        assert "Col1" in result
        assert "Abstract text" in result

    def test_full_paper_structure(self):
        paper = """# PocketHunter Paper

## Abstract

This paper presents a novel approach to pocket detection.

## Introduction

The problem of transient binding pocket detection remains challenging.

## Methods

We used p2rank for pocket detection and DBSCAN for clustering.

## Results

The pipeline achieved strong performance across all test systems.

## Discussion

These results demonstrate the utility of pharmacophore-based ranking."""
        result = cleanup_prose(paper)
        assert "## Abstract" in result
        assert "## Methods" in result
        assert "p2rank" in result
        assert "DBSCAN" in result
        assert result.count("\n\n") >= 4
