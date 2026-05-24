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


from research_assistant.common import read_file
from research_assistant.researcher import (
    CHROMA_DIR,
    DEFAULT_EMBED_MODEL,
    _embed_single,
    _get_collection,
)
from research_assistant.verification.paraphrase_check import split_paragraphs
from research_assistant.verification import external_match as _em

DEFAULT_INTERNAL_THRESHOLD = 0.85
DEFAULT_EXTERNAL_THRESHOLD = 0.80
DEFAULT_MIN_CHARS = 150
DEFAULT_SOURCES: tuple[str, ...] = ("internal", "openalex", "crossref")
EXTERNAL_FETCH_LIMIT = 5


def _internal_matches(paragraph: str, threshold: float) -> list[ExternalMatch]:
    """Cosine-similarity matches against the local Chroma index (your indexed library)."""
    if not CHROMA_DIR.exists():
        return []
    collection = _get_collection()
    emb = _embed_single(paragraph, model=DEFAULT_EMBED_MODEL)
    results = collection.query(
        query_embeddings=[emb],
        n_results=5,
        include=["documents", "metadatas", "distances"],
    )
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    out: list[ExternalMatch] = []
    for doc, meta, dist in zip(docs, metas, dists, strict=False):
        if doc is None or meta is None or dist is None:
            continue
        sim = 1.0 - dist
        if sim < threshold:
            continue
        out.append(
            ExternalMatch(
                source="internal",
                similarity=round(sim, 4),
                title=meta.get("title", "") or "",
                authors=meta.get("authors_short") or None,
                year=int(meta["year"]) if (meta.get("year") or "").isdigit() else None,
                doi=meta.get("doi") or None,
                citekey=meta.get("citekey") or None,
                excerpt=doc[:300],
            )
        )
    return out


def _external_matches_from(source: str, paragraph: str, threshold: float) -> list[ExternalMatch]:
    """Shared OpenAlex/Crossref helper. Cosine sim is computed from abstracts."""
    candidates = _em.cached_search(source, paragraph, limit=EXTERNAL_FETCH_LIMIT)
    if not candidates:
        return []

    para_emb = _embed_single(paragraph, model=DEFAULT_EMBED_MODEL)
    out: list[ExternalMatch] = []
    for cand in candidates:
        abstract = (cand.get("abstract") or "").strip()
        if not abstract:
            continue
        cand_emb = _embed_single(abstract, model=DEFAULT_EMBED_MODEL)
        sim = _cosine(para_emb, cand_emb)
        if sim < threshold:
            continue
        out.append(
            ExternalMatch(
                source=source,                         # type: ignore[arg-type]
                similarity=round(sim, 4),
                title=cand.get("title", "") or "",
                authors=cand.get("authors"),
                year=cand.get("year"),
                doi=cand.get("doi"),
                excerpt=abstract[:300],
                url=cand.get("url"),
            )
        )
    return out


def _external_matches_openalex(paragraph: str, threshold: float) -> list[ExternalMatch]:
    return _external_matches_from("openalex", paragraph, threshold)


def _external_matches_crossref(paragraph: str, threshold: float) -> list[ExternalMatch]:
    return _external_matches_from("crossref", paragraph, threshold)


def _cosine(a: list[float], b: list[float]) -> float:
    import math
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def check_originality(
    draft_path: str,
    *,
    sources: tuple[str, ...] = DEFAULT_SOURCES,
    internal_threshold: float = DEFAULT_INTERNAL_THRESHOLD,
    external_threshold: float = DEFAULT_EXTERNAL_THRESHOLD,
    min_chars: int = DEFAULT_MIN_CHARS,
) -> OriginalityReport:
    """Run all configured sources against every substantive paragraph in the draft."""
    text = read_file(draft_path)
    paragraphs = [p for p in split_paragraphs(text) if len(p) >= min_chars]

    report_paragraphs: list[ParagraphReport] = []
    for i, para in enumerate(paragraphs):
        matches: list[ExternalMatch] = []
        if "internal" in sources:
            matches += _internal_matches(para, internal_threshold)
        if "openalex" in sources:
            matches += _external_matches_openalex(para, external_threshold)
        if "crossref" in sources:
            matches += _external_matches_crossref(para, external_threshold)
        if matches:
            report_paragraphs.append(ParagraphReport(index=i, text=para, matches=matches))

    return OriginalityReport(paragraphs=report_paragraphs)
