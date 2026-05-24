"""Tests for verification.originality."""
from __future__ import annotations

import pytest


@pytest.mark.unit
def test_paragraph_report_severity_thresholds():
    from research_assistant.verification.originality import ExternalMatch, ParagraphReport

    clean = ParagraphReport(index=0, text="x" * 200, matches=[])
    assert clean.severity == "green"

    m_yellow = ExternalMatch(
        source="openalex", similarity=0.85, title="t", authors=None, year=None,
        doi=None, citekey=None, excerpt="", url=None,
    )
    yellow = ParagraphReport(index=1, text="x" * 200, matches=[m_yellow])
    assert yellow.severity == "yellow"

    m_red = m_yellow.model_copy(update={"similarity": 0.95})
    red = ParagraphReport(index=2, text="x" * 200, matches=[m_red])
    assert red.severity == "red"


@pytest.mark.unit
def test_originality_report_summary():
    from research_assistant.verification.originality import (
        ExternalMatch,
        OriginalityReport,
        ParagraphReport,
    )

    matches_red = [ExternalMatch(
        source="internal", similarity=0.95, title="t", authors=None, year=None,
        doi=None, citekey="smith2024", excerpt="", url=None,
    )]
    matches_yellow = [ExternalMatch(
        source="openalex", similarity=0.82, title="t", authors=None, year=None,
        doi=None, citekey=None, excerpt="", url=None,
    )]

    report = OriginalityReport(paragraphs=[
        ParagraphReport(index=0, text="x" * 200, matches=matches_red),
        ParagraphReport(index=1, text="x" * 200, matches=matches_yellow),
        ParagraphReport(index=2, text="x" * 200, matches=[]),
    ])
    assert report.summary == "1 red flag(s), 1 yellow flag(s)"


@pytest.mark.unit
def test_check_originality_runs_internal_and_external(tmp_path, monkeypatch):
    """Given a draft with two paragraphs, check_originality runs the requested
    sources and aggregates matches into ParagraphReport entries."""
    from research_assistant.verification import originality as orig

    draft = tmp_path / "draft.md"
    draft.write_text(
        "First paragraph. " * 30 + "\n\n" + "Second paragraph. " * 30,
        encoding="utf-8",
    )

    # Fake the three source helpers
    def fake_internal(para, threshold):
        return [orig.ExternalMatch(
            source="internal", similarity=0.88, title="Internal hit",
            citekey="smith2024", excerpt=para[:80],
        )]

    def fake_openalex(para, threshold):
        return [orig.ExternalMatch(
            source="openalex", similarity=0.81, title="OpenAlex hit",
            doi="10.1/x", excerpt=para[:80],
        )]

    monkeypatch.setattr(orig, "_internal_matches", fake_internal)
    monkeypatch.setattr(orig, "_external_matches_openalex", fake_openalex)
    monkeypatch.setattr(orig, "_external_matches_crossref", lambda p, t: [])

    report = orig.check_originality(
        str(draft),
        sources=("internal", "openalex", "crossref"),
        internal_threshold=0.85,
        external_threshold=0.80,
        min_chars=50,
    )

    assert len(report.paragraphs) == 2
    for p in report.paragraphs:
        sources_in_matches = {m.source for m in p.matches}
        assert sources_in_matches == {"internal", "openalex"}
    assert report.summary == "0 red flag(s), 2 yellow flag(s)"


@pytest.mark.unit
def test_check_originality_skips_short_paragraphs(tmp_path, monkeypatch):
    from research_assistant.verification import originality as orig

    draft = tmp_path / "draft.md"
    draft.write_text("tiny\n\n" + "long enough paragraph " * 20, encoding="utf-8")

    monkeypatch.setattr(orig, "_internal_matches", lambda p, t: [])
    monkeypatch.setattr(orig, "_external_matches_openalex", lambda p, t: [])
    monkeypatch.setattr(orig, "_external_matches_crossref", lambda p, t: [])

    report = orig.check_originality(str(draft), min_chars=50)
    assert len(report.paragraphs) == 0   # short paragraph filtered, long one has no matches -> not flagged
