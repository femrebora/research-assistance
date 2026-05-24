"""Originality check: combines internal RAG similarity with external academic search.

NOT a true plagiarism detector. Produces leads for human review.

Usage:
    ra-originality drafts/ch1.md
    ra-originality drafts/ch1.md --sources internal,openalex --internal-threshold 0.80
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ExternalMatch(BaseModel):
    """A single match for a paragraph from one source."""

    source: Literal["internal", "openalex", "crossref"]
    similarity: float
    title: str
    authors: str | None = None
    year: int | None = None
    doi: str | None = None
    citekey: str | None = None         # only for internal matches
    excerpt: str = ""                  # snippet that matched
    url: str | None = None


class ParagraphReport(BaseModel):
    index: int
    text: str
    matches: list[ExternalMatch]

    @property
    def severity(self) -> Literal["green", "yellow", "red"]:
        if not self.matches:
            return "green"
        max_sim = max(m.similarity for m in self.matches)
        return "red" if max_sim >= 0.92 else "yellow"


class OriginalityReport(BaseModel):
    paragraphs: list[ParagraphReport]

    @property
    def summary(self) -> str:
        red = sum(1 for p in self.paragraphs if p.severity == "red")
        yellow = sum(1 for p in self.paragraphs if p.severity == "yellow")
        return f"{red} red flag(s), {yellow} yellow flag(s)"
