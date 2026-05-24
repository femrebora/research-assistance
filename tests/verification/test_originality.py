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
        ExternalMatch, OriginalityReport, ParagraphReport,
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
